from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.models.telemetry import Telemetry
from app.models.device import Device
from app.schemas.telemetry import TelemetryIngest, FleetTelemetryRead
from app.core.context import get_request_id
from app.services.alert import alert_service
from app.repositories.telemetry import telemetry_repo
from typing import Optional

logger = structlog.get_logger(__name__)

class TelemetryService:
    @staticmethod
    async def ingest_telemetry(db: AsyncSession, device: Device, payload: TelemetryIngest) -> bool:
        """
        Ingest telemetry with idempotency.
        Returns True if a new record was inserted, False if it was a duplicate.
        """
        try:
            async with db.begin_nested():
                # Create the telemetry DB object
                telemetry_db = Telemetry(
                    device_id=device.id,
                    **payload.model_dump(exclude={"firmware_version"})
                )
                db.add(telemetry_db)
                await db.flush()
        except IntegrityError:
            # Idempotency check: (device_id, timestamp) constraint violation
            logger.info(
                "Duplicate telemetry submission ignored",
                action="TELEMETRY_DUPLICATE_IGNORED",
                device_uid=device.device_uid,
                timestamp=payload.timestamp.isoformat(),
                request_id=get_request_id()
            )
            return False

        # If we reach here, telemetry is fresh and inserted
        # 1. Update device state
        device.last_seen_at = datetime.now(timezone.utc)
        if device.status in ("PROVISIONED", "OFFLINE"):
            previous_status = device.status
            device.status = "ONLINE"
            logger.info(
                "Device is online",
                action="DEVICE_ONLINE",
                device_uid=device.device_uid,
                previous_status=previous_status,
                request_id=get_request_id()
            )
            # A reconnecting device clears its own offline alert.
            if previous_status == "OFFLINE":
                await alert_service.resolve_offline_alerts(db, device)


        if payload.firmware_version:
            device.firmware_version = payload.firmware_version
            
        # 2. Evaluate alerts
        await alert_service.evaluate_telemetry(db, device, payload)
        
        # We don't commit here, we rely on the router or middleware to commit
        
        logger.info(
            "Telemetry ingested",
            action="TELEMETRY_INGESTED",
            device_uid=device.device_uid,
            request_id=get_request_id()
        )
        return True

    @staticmethod
    async def search_fleet_telemetry(
        db: AsyncSession,
        device_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20
    ):
        rows, total = await telemetry_repo.search_fleet_telemetry(
            db, device_id, customer_id, start_date, end_date, skip, limit
        )
        
        items = []
        for row in rows:
            telemetry_model = row[0]
            device_name = row[1]
            device_uid = row[2]
            customer_name = row[3]
            
            telemetry_dict = telemetry_model.__dict__.copy()
            telemetry_dict["device_name"] = device_name
            telemetry_dict["device_uid"] = device_uid
            telemetry_dict["customer_name"] = customer_name
            
            items.append(FleetTelemetryRead.model_validate(telemetry_dict))
            
        return items, total

    @staticmethod
    async def export_fleet_telemetry(
        db: AsyncSession,
        device_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[dict]:
        # Export up to 5000 rows for fleet
        rows, _ = await telemetry_repo.search_fleet_telemetry(
            db, device_id, customer_id, start_date, end_date, 0, 5000
        )
        
        export_data = []
        for row in rows:
            t = row[0]
            export_data.append({
                "device_name": row[1],
                "device_uid": row[2],
                "customer_name": row[3],
                "timestamp": t.timestamp.isoformat(),
                "battery_percentage": t.battery_percentage,
                "battery_voltage": t.battery_voltage,
                "panel_voltage": t.panel_voltage,
                "charging_current": t.charging_current,
                "load_current": t.load_current,
                "temperature": t.temperature,
                "humidity": t.humidity,
                "signal_strength": t.signal_strength,
                "light_load_status": t.light_load_status
            })
        return export_data

telemetry_service = TelemetryService()
