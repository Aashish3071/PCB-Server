import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_provision_device(client: AsyncClient):
    # Create customer first
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "Device Owner"})
    cust_id = cust_resp.json()["id"]

    # Provision device
    payload = {
        "customer_id": cust_id,
        "device_name": "Pole-A1",
        "device_type": "solar_rms"
    }
    response = await client.post("/api/v1/devices", json=payload)
    assert response.status_code == 201
    data = response.json()
    
    assert data["device_name"] == "Pole-A1"
    assert "device_uid" in data
    assert data["device_uid"].startswith("SLRMS-")
    assert data["status"] == "PROVISIONED"
    
    # Critical checks: Plaintext API key must be present in response
    assert "api_key_plaintext" in data
    assert len(data["api_key_plaintext"]) > 10

@pytest.mark.asyncio
async def test_api_key_stored_as_hash(client: AsyncClient, db_session):
    from app.models.device import Device
    from sqlalchemy import select
    
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "Hash Check Owner"})
    cust_id = cust_resp.json()["id"]

    payload = {
        "customer_id": cust_id,
        "device_name": "Pole-Hash"
    }
    response = await client.post("/api/v1/devices", json=payload)
    data = response.json()
    plaintext_key = data["api_key_plaintext"]
    device_id = data["id"]
    
    # Check DB directly to ensure plaintext is not there
    result = await db_session.execute(select(Device).filter_by(id=device_id))
    db_device = result.scalars().first()
    
    assert db_device is not None
    assert db_device.api_key_hash is not None
    assert db_device.api_key_hash != plaintext_key
    assert plaintext_key not in db_device.api_key_hash

@pytest.mark.asyncio
async def test_get_device_by_uid(client: AsyncClient):
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "UID Check"})
    cust_id = cust_resp.json()["id"]

    prov_resp = await client.post("/api/v1/devices", json={
        "customer_id": cust_id,
        "device_name": "Pole-UID"
    })
    device_uid = prov_resp.json()["device_uid"]

    # Test the new endpoint
    response = await client.get(f"/api/v1/devices/by-uid/{device_uid}")
    assert response.status_code == 200
    data = response.json()
    assert data["device_uid"] == device_uid
    
    # Ensure plaintext key is NOT returned on read
    assert "api_key_plaintext" not in data

@pytest.mark.asyncio
async def test_rotate_api_key(client: AsyncClient):
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "Rotation Owner"})
    cust_id = cust_resp.json()["id"]

    prov_resp = await client.post("/api/v1/devices", json={
        "customer_id": cust_id,
        "device_name": "Pole-Rotate"
    })
    device_id = prov_resp.json()["id"]
    old_key = prov_resp.json()["api_key_plaintext"]

    # Rotate
    rotate_resp = await client.post(f"/api/v1/devices/{device_id}/rotate-key")
    assert rotate_resp.status_code == 200
    new_key = rotate_resp.json()["api_key_plaintext"]
    
    assert new_key != old_key

@pytest.mark.asyncio
async def test_delete_customer_with_devices(client: AsyncClient):
    # Setup
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "Conflict Owner"})
    cust_id = cust_resp.json()["id"]
    await client.post("/api/v1/devices", json={"customer_id": cust_id, "device_name": "Conflicting Device"})

    # Attempt delete
    delete_resp = await client.delete(f"/api/v1/customers/{cust_id}")
    assert delete_resp.status_code == 409
    assert "Cannot delete customer with assigned devices" in delete_resp.json()["detail"]

@pytest.mark.asyncio
async def test_concurrent_device_uid_generation(client: AsyncClient):
    # Setup customer
    cust_resp = await client.post("/api/v1/customers", json={"company_name": "Concurrent Owner"})
    cust_id = cust_resp.json()["id"]

    payload = {"customer_id": cust_id, "device_name": "Concurrent-Pole"}

    # We cannot use the exact same device_name since there's a unique constraint on (customer_id, device_name).
    # So we generate dynamic payloads.
    tasks = []
    for i in range(10):
        tasks.append(client.post("/api/v1/devices", json={
            "customer_id": cust_id,
            "device_name": f"Concurrent-Pole-{i}"
        }))

    responses = await asyncio.gather(*tasks)
    
    uids = set()
    for resp in responses:
        assert resp.status_code == 201
        uid = resp.json()["device_uid"]
        uids.add(uid)
        
    # Ensure exactly 10 unique UIDs were generated
    assert len(uids) == 10
