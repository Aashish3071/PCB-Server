import asyncio
import httpx
import json
from datetime import datetime, timezone

from app.database.session import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.device import Device
import os

async def test_golden_path():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # 1. Get credentials from provisioning cache
    state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../simulator/state/provisioning.json'))
    with open(state_file, 'r') as f:
        provisioned = json.load(f)
        
    target_creds = provisioned[0]
    device_uid = target_creds["device_uid"]
    api_key = target_creds["api_key"]
    print(f"Testing with device {device_uid}")

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 2. Upload valid telemetry
        print("Uploading valid telemetry...")
        tel_resp = await client.post("/api/v1/telemetry", json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "battery_percentage": 100,
            "signal_strength": 50
        }, headers={"X-Device-UID": device_uid, "X-API-Key": api_key})
        print(f"Valid upload response: {tel_resp.status_code}")
        assert tel_resp.status_code == 200

        # 3. Disable device directly via Database
        print("Disabling device...")
        async with async_session() as session:
            result = await session.execute(select(Device).filter_by(device_uid=device_uid))
            device = result.scalar_one_or_none()
            assert device is not None
            device.status = "DISABLED"
            await session.commit()
        print("Device disabled in database.")

        # 4. Upload telemetry again (should be rejected)
        print("Uploading telemetry to disabled device...")
        tel_resp = await client.post("/api/v1/telemetry", json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "battery_percentage": 95,
            "signal_strength": 55
        }, headers={"X-Device-UID": device_uid, "X-API-Key": api_key})
        print(f"Disabled upload response: {tel_resp.status_code} {tel_resp.text}")
        assert tel_resp.status_code == 403 or tel_resp.status_code == 400

        # 5. Verify system health
        print("Checking system health...")
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200
        print(f"Health: {health_resp.json()}")

        print("Golden Path Complete!")

if __name__ == "__main__":
    asyncio.run(test_golden_path())
