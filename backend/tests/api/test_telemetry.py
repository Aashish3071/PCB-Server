import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from datetime import datetime, timezone, timedelta

from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.alert import Alert

pytestmark = pytest.mark.asyncio

async def test_ingest_telemetry_success(client: AsyncClient, db_session: AsyncSession):
    # Retrieve raw api key from test fixture or use the fixture directly if it includes the plaintext key.
    # Wait, the test_device fixture doesn't give us the plaintext key natively. 
    # Let's create a device explicitly in the test for full control.
    from app.services.device import device_service
    from app.schemas.device import DeviceCreate
    from app.repositories.customer import customer_repo
    from app.schemas.customer import CustomerCreate
    
    customer = await customer_repo.create(db_session, obj_in=CustomerCreate(company_name="Test Corp", contact_person="John", email="john@test.com"))
    device, plaintext_key = await device_service.provision_device(db_session, obj_in=DeviceCreate(customer_id=customer.id, device_name="Test Device"))
    
    headers = {
        "X-Device-UID": device.device_uid,
        "X-API-Key": plaintext_key,
        "X-Telemetry-Version": "1"
    }
    
    now = datetime.now(timezone.utc)
    payload = {
        "timestamp": now.isoformat(),
        "temperature": 25.5,
        "humidity": 60.0,
        "battery_voltage": 12.5,
        "battery_percentage": 85.0,
        "firmware_version": "v1.2.3"
    }
    
    response = await client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["next_upload_seconds"] == 300
    
    # Verify DB state
    await db_session.refresh(device)
    assert device.status == "ONLINE"
    assert device.firmware_version == "v1.2.3"
    assert device.last_seen_at is not None
    
    # Verify telemetry row
    result = await db_session.execute(select(Telemetry).where(Telemetry.device_id == device.id))
    telemetry_rows = result.scalars().all()
    assert len(telemetry_rows) == 1
    assert telemetry_rows[0].temperature == 25.5


async def test_ingest_telemetry_invalid_auth(client: AsyncClient, db_session: AsyncSession):
    from app.services.device import device_service
    from app.schemas.device import DeviceCreate
    from app.repositories.customer import customer_repo
    from app.schemas.customer import CustomerCreate
    
    customer = await customer_repo.create(db_session, obj_in=CustomerCreate(company_name="Test Auth", email="auth@test.com"))
    device, plaintext_key = await device_service.provision_device(db_session, obj_in=DeviceCreate(customer_id=customer.id, device_name="Test Auth Dev"))
    
    headers = {
        "X-Device-UID": device.device_uid,
        "X-API-Key": "wrong_key"
    }
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": 25.5
    }
    
    response = await client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert response.status_code == 401


async def test_ingest_telemetry_idempotency(client: AsyncClient, db_session: AsyncSession):
    from app.services.device import device_service
    from app.schemas.device import DeviceCreate
    from app.repositories.customer import customer_repo
    from app.schemas.customer import CustomerCreate
    
    customer = await customer_repo.create(db_session, obj_in=CustomerCreate(company_name="Test Idem", email="idem@test.com"))
    device, plaintext_key = await device_service.provision_device(db_session, obj_in=DeviceCreate(customer_id=customer.id, device_name="Test Idem Dev"))
    
    headers = {
        "X-Device-UID": device.device_uid,
        "X-API-Key": plaintext_key
    }
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": 25.5
    }
    
    # First request
    r1 = await client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert r1.status_code == 200

    # Second request (exact same timestamp). Clear the rate limiter so this
    # test stays focused on DB-level idempotency, not throttling.
    from app.utils.rate_limit import telemetry_rate_limiter
    telemetry_rate_limiter._hits.clear()
    r2 = await client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert r2.status_code == 200
    
    # Verify only ONE telemetry record exists
    result = await db_session.execute(select(Telemetry).where(Telemetry.device_id == device.id))
    telemetry_rows = result.scalars().all()
    assert len(telemetry_rows) == 1


async def test_ingest_telemetry_alerts(client: AsyncClient, db_session: AsyncSession):
    from app.services.device import device_service
    from app.schemas.device import DeviceCreate
    from app.repositories.customer import customer_repo
    from app.schemas.customer import CustomerCreate
    
    customer = await customer_repo.create(db_session, obj_in=CustomerCreate(company_name="Test Alerts", email="alerts@test.com"))
    device, plaintext_key = await device_service.provision_device(db_session, obj_in=DeviceCreate(customer_id=customer.id, device_name="Test Alerts Dev"))
    
    headers = {
        "X-Device-UID": device.device_uid,
        "X-API-Key": plaintext_key
    }
    
    # Trigger low battery alert (< 20%)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "battery_percentage": 15.0
    }
    
    response = await client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Verify alert was created
    result = await db_session.execute(select(Alert).where(Alert.device_id == device.id))
    alerts = result.scalars().all()
    
    assert len(alerts) == 1
    assert alerts[0].alert_type == "LOW_BATTERY"
    assert alerts[0].severity == "WARNING"
    assert "15.0" in alerts[0].message
