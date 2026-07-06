import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.models.device import Device
from app.models.alert import Alert
from app.services.device import device_service
from app.schemas.device import DeviceCreate
from app.repositories.customer import customer_repo
from app.schemas.customer import CustomerCreate
from app.workers.offline_watchdog import mark_stale_devices_offline
from app.utils.rate_limit import telemetry_rate_limiter

pytestmark = pytest.mark.asyncio


async def _provision(db: AsyncSession, name: str, **device_kwargs):
    customer = await customer_repo.create(
        db, obj_in=CustomerCreate(
            company_name=f"{name} Corp", contact_person="Jane", email=f"{name.lower()}@test.com"
        )
    )
    device, key = await device_service.provision_device(
        db, obj_in=DeviceCreate(customer_id=customer.id, device_name=name, **device_kwargs)
    )
    await db.commit()
    return device, key


def _auth_headers(device: Device, key: str) -> dict:
    return {"X-Device-UID": device.device_uid, "X-API-Key": key}


async def test_offline_device_reconnects_and_resolves_alert(client: AsyncClient, db_session: AsyncSession):
    device, key = await _provision(db_session, "Reconnector")

    # Simulate the watchdog having flagged it: OFFLINE with an open alert.
    device.status = "OFFLINE"
    db_session.add(Alert(
        device_id=device.id,
        alert_type="DEVICE_OFFLINE",
        severity="CRITICAL",
        message="Device stopped reporting"
    ))
    await db_session.commit()

    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "battery_percentage": 80.0}
    response = await client.post("/api/v1/telemetry", json=payload, headers=_auth_headers(device, key))
    assert response.status_code == 200

    await db_session.refresh(device)
    assert device.status == "ONLINE"

    result = await db_session.execute(
        select(Alert).where(Alert.device_id == device.id, Alert.alert_type == "DEVICE_OFFLINE")
    )
    alert = result.scalar_one()
    assert alert.is_resolved is True
    assert alert.resolved_at is not None


async def test_watchdog_marks_stale_device_offline(client: AsyncClient, db_session: AsyncSession):
    device, key = await _provision(db_session, "Staler")

    # Bring it ONLINE via a real upload.
    payload = {"timestamp": datetime.now(timezone.utc).isoformat()}
    response = await client.post("/api/v1/telemetry", json=payload, headers=_auth_headers(device, key))
    assert response.status_code == 200
    await db_session.refresh(device)
    assert device.status == "ONLINE"

    # Sweep "in the future", past interval * grace multiplier (300s * 3).
    future = datetime.now(timezone.utc) + timedelta(seconds=1000)
    count = await mark_stale_devices_offline(db_session, now=future)
    await db_session.commit()
    assert count == 1

    await db_session.refresh(device)
    assert device.status == "OFFLINE"

    result = await db_session.execute(
        select(Alert).where(
            Alert.device_id == device.id,
            Alert.alert_type == "DEVICE_OFFLINE",
            Alert.is_resolved.is_(False)
        )
    )
    assert result.scalar_one() is not None

    # A second sweep must not duplicate the alert or re-count the device.
    count = await mark_stale_devices_offline(db_session, now=future)
    assert count == 0
    result = await db_session.execute(
        select(Alert).where(Alert.device_id == device.id, Alert.alert_type == "DEVICE_OFFLINE")
    )
    assert len(result.scalars().all()) == 1


async def test_watchdog_leaves_fresh_device_online(client: AsyncClient, db_session: AsyncSession):
    device, key = await _provision(db_session, "Freshy")

    payload = {"timestamp": datetime.now(timezone.utc).isoformat()}
    response = await client.post("/api/v1/telemetry", json=payload, headers=_auth_headers(device, key))
    assert response.status_code == 200

    # Sweep "now": device just reported, well inside the grace window.
    count = await mark_stale_devices_offline(db_session)
    await db_session.commit()

    await db_session.refresh(device)
    assert device.status == "ONLINE"
    assert count == 0


async def test_per_device_upload_interval(client: AsyncClient, db_session: AsyncSession):
    # Provision with a custom interval and verify the device is told about it.
    device, key = await _provision(db_session, "FastReporter", upload_interval_seconds=60)

    payload = {"timestamp": datetime.now(timezone.utc).isoformat()}
    response = await client.post("/api/v1/telemetry", json=payload, headers=_auth_headers(device, key))
    assert response.status_code == 200
    assert response.json()["next_upload_seconds"] == 60

    # Admin retunes the interval remotely; the device picks it up on next upload.
    response = await client.put(
        f"/api/v1/devices/{device.id}", json={"upload_interval_seconds": 900}
    )
    assert response.status_code == 200
    assert response.json()["upload_interval_seconds"] == 900

    # This test is exercising the interval-config channel, not rate limiting.
    telemetry_rate_limiter._hits.clear()
    payload = {"timestamp": (datetime.now(timezone.utc) + timedelta(seconds=61)).isoformat()}
    response = await client.post("/api/v1/telemetry", json=payload, headers=_auth_headers(device, key))
    assert response.status_code == 200
    assert response.json()["next_upload_seconds"] == 900


async def test_upload_interval_validation(client: AsyncClient, db_session: AsyncSession):
    device, _ = await _provision(db_session, "Validated")

    # Below the 30s floor — rejected.
    response = await client.put(
        f"/api/v1/devices/{device.id}", json={"upload_interval_seconds": 5}
    )
    assert response.status_code == 422
