import asyncio
import argparse
import secrets
import json
import os
from uuid import uuid4
from dotenv import load_dotenv
load_dotenv()

from app.database.session import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.customer import Customer
from app.models.device import Device
from app.utils.security import get_password_hash

async def seed_devices(count: int):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create a customer
        customer = Customer(
            id=uuid4(),
            company_name="Simulator Fleet Customer"
        )
        session.add(customer)
        await session.flush()

        provisioned_devices = []
        for i in range(count):
            api_key = secrets.token_urlsafe(32)
            device = Device(
                id=uuid4(),
                customer_id=customer.id,
                device_uid=f"SIM-{uuid4().hex[:8].upper()}",
                device_name=f"Simulated Pole {i+1}",
                device_type="solar_rms",
                api_key_hash=get_password_hash(api_key)
            )
            session.add(device)
            provisioned_devices.append({
                "device_uid": device.device_uid,
                "api_key": api_key
            })
            
        await session.commit()
        
        # Write to simulator state
        state_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../simulator/state'))
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, 'provisioning.json')
        
        with open(state_file, 'w') as f:
            json.dump(provisioned_devices, f, indent=2)
            
        print(f"Successfully provisioned {count} devices and saved to {state_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(seed_devices(args.count))
