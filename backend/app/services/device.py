import structlog
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
import asyncio

from app.core.context import get_request_id
from app.repositories.device import device_repo
from app.repositories.customer import customer_repo
from app.repositories.telemetry import telemetry_repo
from app.repositories.alert import alert_repo
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceListRead, DeviceRead, DeviceOverviewResponse
from app.schemas.telemetry import TelemetryRead
from app.schemas.alert import AlertRead
from app.models.device import Device
from app.utils.security import generate_api_key, get_password_hash

logger = structlog.get_logger(__name__)

class DeviceService:
    @staticmethod
    async def get_device(db: AsyncSession, id: UUID) -> Device:
        device = await device_repo.get(db, id)
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        return device

    async def get_device_overview(self, db: AsyncSession, device_id: UUID) -> DeviceOverviewResponse:
        # Get base device detailed
        device_row = await device_repo.search_detailed(db, query_str=str(device_id))
        items, _ = device_row
        if not items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        
        device_model = items[0][0]
        customer_name = items[0][1]
        latest_telemetry = items[0][2]
        
        device_dict = {
            "id": device_model.id,
            "device_uid": device_model.device_uid,
            "customer_id": device_model.customer_id,
            "device_name": device_model.device_name,
            "device_type": device_model.device_type,
            "firmware_version": device_model.firmware_version,
            "installation_location": device_model.installation_location,
            "status": device_model.status,
            "upload_interval_seconds": device_model.upload_interval_seconds,
            "last_seen_at": device_model.last_seen_at,
            "created_at": device_model.created_at,
            "updated_at": device_model.updated_at,
            "customer_name": customer_name,
            "battery_percentage": latest_telemetry.battery_percentage if latest_telemetry else None,
            "signal_strength": latest_telemetry.signal_strength if latest_telemetry else None
        }
        device_list_read = DeviceListRead.model_validate(device_dict)

        # Analytics since 24 hours ago
        since_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Concurrent fetches
        analytics_task = telemetry_repo.get_device_analytics(db, device_id, since=since_time)
        alerts_task = alert_repo.get_recent_alerts(db, device_id, limit=5)
        
        analytics, alerts = await asyncio.gather(analytics_task, alerts_task)
        
        return DeviceOverviewResponse(
            device=device_list_read,
            latest_telemetry=TelemetryRead.model_validate(latest_telemetry) if latest_telemetry else None,
            analytics=analytics,
            recent_alerts=[AlertRead.model_validate(a) for a in alerts]
        )

    async def get_device_telemetry(self, db: AsyncSession, device_id: UUID, skip: int, limit: int):
        device = await self.get_device(db, device_id)
        return await telemetry_repo.get_device_telemetry_paginated(db, device_id, skip, limit)

    async def export_device_data(self, db: AsyncSession, device_id: UUID) -> dict:
        device = await self.get_device(db, device_id)
        # Fetch overview for context
        overview = await self.get_device_overview(db, device_id)
        # Fetch all telemetry (or last N days, we'll fetch up to 1000 records for the export)
        items, _ = await telemetry_repo.get_device_telemetry_paginated(db, device_id, 0, 1000)
        
        telemetry_data = [TelemetryRead.model_validate(t).model_dump(mode="json") for t in items]
        overview_data = overview.model_dump(mode="json")
        
        return {
            "overview": overview_data,
            "telemetry_history": telemetry_data
        }

    @staticmethod
    async def provision_device(db: AsyncSession, obj_in: DeviceCreate) -> tuple[Device, str]:
        """
        Provisions a new device by generating a sequential UID and a secure API key.
        Returns the provisioned device and the plaintext API key (to be shown once).
        """
        # 1. Generate concurrency-safe sequential UID using Postgres sequence
        result = await db.execute(text("SELECT nextval('device_uid_seq')"))
        next_num = result.scalar()
        next_uid = f"SLRMS-{str(next_num).zfill(6)}"
        
        # 2. Generate secure API key
        plaintext_key = generate_api_key()
        hashed_key = get_password_hash(plaintext_key)
        
        # 3. Create the database record
        device_data = obj_in.model_dump()
        
        # Create a dictionary suitable for SQLAlchemy instantiation
        db_obj_in = {
            **device_data,
            "device_uid": next_uid,
            "api_key_hash": hashed_key,
            "status": "PROVISIONED"
        }
        
        device = await device_repo.create(db, obj_in=db_obj_in)
        
        logger.info(
            "Device provisioned",
            action="PROVISION_DEVICE",
            device_uid=next_uid,
            customer_id=str(obj_in.customer_id),
            request_id=get_request_id()
        )
        return device, plaintext_key

    @staticmethod
    async def update_device(db: AsyncSession, id: UUID, obj_in: DeviceUpdate) -> Device:
        device = await DeviceService.get_device(db, id)
        
        if obj_in.status and obj_in.status != device.status:
            logger.info(
                "Device status updated",
                action="UPDATE_DEVICE_STATUS",
                device_uid=device.device_uid,
                old_status=device.status,
                new_status=obj_in.status,
                request_id=get_request_id()
            )
            
        return await device_repo.update(db, db_obj=device, obj_in=obj_in)

    @staticmethod
    async def delete_device(db: AsyncSession, id: UUID) -> Device:
        device = await DeviceService.get_device(db, id)
        # Note: Do we prevent deletion if telemetry exists?
        # The MVP didn't specify, but standard practice is to allow it with cascading or deny it.
        # SQLAlchemy models aren't using cascading delete right now. So it will fail at DB level if telemetry exists.
        # This is fine for MVP.
        return await device_repo.remove(db, id=id)

    @staticmethod
    async def rotate_api_key(db: AsyncSession, id: UUID) -> str:
        """
        Rotates the API key for a device.
        Returns the new plaintext API key.
        """
        device = await DeviceService.get_device(db, id)
        
        plaintext_key = generate_api_key()
        hashed_key = get_password_hash(plaintext_key)
        
        # Update the device hash using the repository update bypassing the Pydantic schema
        await device_repo.update(db, db_obj=device, obj_in={"api_key_hash": hashed_key})
        
        logger.warning(
            "API key rotated",
            action="ROTATE_API_KEY",
            device_uid=device.device_uid,
            request_id=get_request_id()
        )
        
        return plaintext_key

    @staticmethod
    async def search_devices(
        db: AsyncSession,
        query_str: str | None = None,
        customer_id: UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[list[DeviceListRead], int]:
        
        results, total = await device_repo.search_detailed(
            db,
            query_str=query_str,
            customer_id=customer_id,
            status=status,
            skip=skip,
            limit=limit,
            sort=sort,
            order=order
        )
        
        # Map the tuples (Device, customer_name, battery, signal) to DeviceListRead
        mapped_results = []
        for device, customer_name, battery, signal in results:
            device_dict = {
                "id": device.id,
                "device_uid": device.device_uid,
                "customer_id": device.customer_id,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "firmware_version": device.firmware_version,
                "installation_location": device.installation_location,
                "status": device.status,
                "upload_interval_seconds": device.upload_interval_seconds,
                "last_seen_at": device.last_seen_at,
                "created_at": device.created_at,
                "updated_at": device.updated_at,
                "customer_name": customer_name,
                "battery_percentage": battery,
                "signal_strength": signal
            }
            mapped_results.append(DeviceListRead.model_validate(device_dict))
            
        return mapped_results, total

device_service = DeviceService()
