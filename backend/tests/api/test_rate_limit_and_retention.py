import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta

from app.models.telemetry import Telemetry
from app.models.alert import Alert
from app.services.device import device_service
from app.schemas.device import DeviceCreate
from app.repositories.customer import customer_repo
from app.schemas.customer import CustomerCreate
from app.utils.rate_limit import TelemetryRateLimiter, telemetry_rate_limiter
from app.workers.retention import prune_telemetry, prune_resolved_alerts

pytestmark = pytest.mark.asyncio


async def _provision(db: AsyncSession, name: str, **kwargs):
    customer = await customer_repo.create(
        db, obj_in=CustomerCreate(
            company_name=f"{name} Corp", contact_person="Jane", email=f"{name.lower()}@t.com"
        )
    )
    device, key = await device_service.provision_device(
        db, obj_in=DeviceCreate(customer_id=customer.id, device_name=name, **kwargs)
    )
    await db.commit()
    return device, key


# --- Rate limiter unit tests (no HTTP) -----------------------------------------

async def test_rate_limiter_allows_normal_cadence():
    limiter = TelemetryRateLimiter(floor_multiplier=0.5, burst_window_seconds=60, burst_limit=5)
    decision = await limiter.check("DEV-1", upload_interval_seconds=300)
    assert decision.allowed
    assert decision.remaining == 4


async def test_rate_limiter_rejects_faster_than_floor():
    limiter = TelemetryRateLimiter(floor_multiplier=0.5, burst_window_seconds=60, burst_limit=100)
    # First one succeeds.
    d1 = await limiter.check("DEV-2", upload_interval_seconds=300)
    assert d1.allowed
    # Immediate second upload is well below the 150s floor.
    d2 = await limiter.check("DEV-2", upload_interval_seconds=300)
    assert not d2.allowed
    assert d2.retry_after_seconds >= 1


async def test_rate_limiter_burst_window_full():
    limiter = TelemetryRateLimiter(floor_multiplier=0.0, burst_window_seconds=60, burst_limit=3)
    for _ in range(3):
        d = await limiter.check("DEV-3", upload_interval_seconds=10)
        assert d.allowed
    d = await limiter.check("DEV-3", upload_interval_seconds=10)
    assert not d.allowed
    assert d.retry_after_seconds >= 1


async def test_rate_limiter_isolates_devices():
    limiter = TelemetryRateLimiter(floor_multiplier=0.5, burst_window_seconds=60, burst_limit=1)
    assert (await limiter.check("A", 10)).allowed
    assert not (await limiter.check("A", 10)).allowed
    # A different device is unaffected.
    assert (await limiter.check("B", 10)).allowed


# --- Rate limiter end-to-end via HTTP ------------------------------------------

async def test_telemetry_endpoint_returns_429(client: AsyncClient, db_session: AsyncSession):
    device, key = await _provision(db_session, "Bursty", upload_interval_seconds=300)
    headers = {"X-Device-UID": device.device_uid, "X-API-Key": key}

    # First upload succeeds.
    r = await client.post("/api/v1/telemetry", json={"timestamp": datetime.now(timezone.utc).isoformat()}, headers=headers)
    assert r.status_code == 200

    # Immediate second upload should be rejected (150s floor).
    r = await client.post("/api/v1/telemetry", json={"timestamp": datetime.now(timezone.utc).isoformat()}, headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


# --- Retention worker ----------------------------------------------------------

async def test_prune_telemetry_removes_old_rows(client: AsyncClient, db_session: AsyncSession):
    device, key = await _provision(db_session, "Ancient")

    now = datetime.now(timezone.utc)
    # Directly insert two rows: one ancient (100 days old), one recent.
    db_session.add(Telemetry(device_id=device.id, timestamp=now - timedelta(days=100)))
    db_session.add(Telemetry(device_id=device.id, timestamp=now - timedelta(days=5)))
    await db_session.commit()

    deleted = await prune_telemetry(db_session)
    assert deleted == 1

    remaining = (await db_session.execute(
        select(func.count()).select_from(Telemetry).where(Telemetry.device_id == device.id)
    )).scalar_one()
    assert remaining == 1


async def test_prune_alerts_keeps_unresolved(client: AsyncClient, db_session: AsyncSession):
    device, _ = await _provision(db_session, "AlertKeeper")
    now = datetime.now(timezone.utc)

    # 3 old alerts: one resolved (should be pruned), two unresolved (kept).
    db_session.add(Alert(
        device_id=device.id, alert_type="LOW_BATTERY", severity="WARNING", message="old resolved",
        is_resolved=True, resolved_at=now - timedelta(days=200)
    ))
    db_session.add(Alert(
        device_id=device.id, alert_type="LOW_BATTERY", severity="WARNING", message="old unresolved",
        is_resolved=False
    ))
    db_session.add(Alert(
        device_id=device.id, alert_type="HIGH_TEMPERATURE", severity="CRITICAL", message="fresh resolved",
        is_resolved=True, resolved_at=now - timedelta(days=10)
    ))
    await db_session.commit()

    deleted = await prune_resolved_alerts(db_session)
    assert deleted == 1

    remaining = (await db_session.execute(
        select(func.count()).select_from(Alert).where(Alert.device_id == device.id)
    )).scalar_one()
    assert remaining == 2


# --- Diagnostics endpoint ------------------------------------------------------

async def test_diagnostics_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Ensure at least one device exists so fleet_by_status has content.
    device, _ = await _provision(db_session, "DiagDevice")

    r = await client.get("/api/v1/diagnostics")
    assert r.status_code == 200
    data = r.json()
    assert "fleet_by_status" in data
    assert "rate_limiter" in data
    assert "config" in data
    assert data["config"]["telemetry_retention_days"] == 90
