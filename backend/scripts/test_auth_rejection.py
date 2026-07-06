import asyncio
import httpx
from datetime import datetime, timezone

async def test_rejections():
    # 1. Invalid Authentication
    print("Testing invalid authentication...")
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {"battery": 95, "panel_voltage": 18.5, "temperature": 25, "humidity": 60},
            "signal_strength": -70
        }
        headers = {
            "X-Device-UID": "SIM-INVALID",
            "X-API-Key": "invalid-key"
        }
        resp = await client.post("/api/v1/telemetry", json=payload, headers=headers)
        print(f"Invalid Auth Response: {resp.status_code} {resp.text}")
        assert resp.status_code == 401, "Should be rejected with 401"
        
    print("All rejection tests passed!")

if __name__ == "__main__":
    asyncio.run(test_rejections())
