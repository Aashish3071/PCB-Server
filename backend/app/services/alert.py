from datetime import datetime, timezone
from uuid import UUID
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.device import Device
from app.schemas.telemetry import TelemetryIngest
from app.schemas.alert import AlertListRead
from app.core.settings import settings
from app.models.alert import Alert
from app.repositories.alert import alert_repo

logger = structlog.get_logger(__name__)

class AlertService:
    @staticmethod
    async def evaluate_telemetry(db: AsyncSession, device: Device, telemetry_in: TelemetryIngest):
        """
        Evaluate telemetry for basic alert conditions using configuration thresholds.
        Creates an alert if conditions are met.
        """
        alerts_to_create = []

        # Low Battery
        if telemetry_in.battery_percentage is not None:
            if telemetry_in.battery_percentage < settings.ALERT_LOW_BATTERY_PCT:
                alerts_to_create.append(
                    Alert(
                        device_id=device.id,
                        alert_type="LOW_BATTERY",
                        severity="WARNING",
                        message=f"Battery is low: {telemetry_in.battery_percentage}% (Threshold: {settings.ALERT_LOW_BATTERY_PCT}%)",
                        metadata_={"battery_percentage": telemetry_in.battery_percentage}
                    )
                )

        # High Temperature
        if telemetry_in.temperature is not None:
            if telemetry_in.temperature > settings.ALERT_HIGH_TEMP_C:
                alerts_to_create.append(
                    Alert(
                        device_id=device.id,
                        alert_type="HIGH_TEMPERATURE",
                        severity="CRITICAL",
                        message=f"Temperature is high: {telemetry_in.temperature}°C (Threshold: {settings.ALERT_HIGH_TEMP_C}°C)",
                        metadata_={"temperature": telemetry_in.temperature}
                    )
                )

        # Low Voltage
        if telemetry_in.battery_voltage is not None:
            if telemetry_in.battery_voltage < settings.ALERT_LOW_VOLTAGE_V:
                alerts_to_create.append(
                    Alert(
                        device_id=device.id,
                        alert_type="LOW_VOLTAGE",
                        severity="WARNING",
                        message=f"Battery voltage is low: {telemetry_in.battery_voltage}V (Threshold: {settings.ALERT_LOW_VOLTAGE_V}V)",
                        metadata_={"battery_voltage": telemetry_in.battery_voltage}
                    )
                )

        if alerts_to_create:
            db.add_all(alerts_to_create)
            logger.info(
                "Generated alerts from telemetry",
                action="ALERTS_GENERATED",
                device_uid=device.device_uid,
                alert_count=len(alerts_to_create)
            )

    @staticmethod
    async def create_offline_alert(db: AsyncSession, device: Device) -> bool:
        """
        Create a DEVICE_OFFLINE alert unless one is already open for the device.
        Returns True if a new alert was created.
        """
        existing = await db.execute(
            select(Alert.id).where(
                Alert.device_id == device.id,
                Alert.alert_type == "DEVICE_OFFLINE",
                Alert.is_resolved.is_(False)
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            return False

        last_seen = device.last_seen_at.isoformat() if device.last_seen_at else "never"
        db.add(Alert(
            device_id=device.id,
            alert_type="DEVICE_OFFLINE",
            severity="CRITICAL",
            message=f"Device stopped reporting (last seen: {last_seen}, expected every {device.upload_interval_seconds}s)",
            metadata_={
                "last_seen_at": last_seen,
                "upload_interval_seconds": device.upload_interval_seconds
            }
        ))
        return True

    @staticmethod
    async def resolve_offline_alerts(db: AsyncSession, device: Device) -> None:
        """Auto-resolve open DEVICE_OFFLINE alerts when a device reconnects."""
        result = await db.execute(
            update(Alert)
            .where(
                Alert.device_id == device.id,
                Alert.alert_type == "DEVICE_OFFLINE",
                Alert.is_resolved.is_(False)
            )
            .values(is_resolved=True, resolved_at=datetime.now(timezone.utc))
        )
        if result.rowcount:
            logger.info(
                "Auto-resolved offline alerts on reconnect",
                action="OFFLINE_ALERTS_RESOLVED",
                device_uid=device.device_uid,
                resolved_count=result.rowcount
            )

    async def search_alerts(self, db: AsyncSession, query_str: str | None, status: str | None, skip: int, limit: int, sort: str, order: str, customer_id: UUID | None = None):
        rows, total = await alert_repo.search_alerts(
            db, query_str, status, customer_id=customer_id,
            skip=skip, limit=limit, sort=sort, order=order
        )
        
        items = []
        for row in rows:
            alert_model = row[0]
            device_name = row[1]
            device_uid = row[2]
            customer_name = row[3]
            
            alert_dict = {
                "id": alert_model.id,
                "device_id": alert_model.device_id,
                "alert_type": alert_model.alert_type,
                "severity": alert_model.severity,
                "message": alert_model.message,
                "metadata_": alert_model.metadata_,
                "is_resolved": alert_model.is_resolved,
                "created_at": alert_model.created_at,
                "resolved_at": alert_model.resolved_at,
                "device_name": device_name,
                "device_uid": device_uid,
                "customer_name": customer_name
            }
            items.append(AlertListRead.model_validate(alert_dict))
            
        return items, total

    async def resolve_alert(self, db: AsyncSession, alert_id: UUID):
        alert = await alert_repo.get(db, id=alert_id)
        if not alert:
            return None
        
        alert.is_resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        return alert

alert_service = AlertService()
