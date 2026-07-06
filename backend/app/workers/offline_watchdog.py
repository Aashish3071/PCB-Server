"""
Offline watchdog: periodically marks silent devices OFFLINE and raises a
DEVICE_OFFLINE alert. Counterpart of the ONLINE transition in
TelemetryService.ingest_telemetry (which also auto-resolves the alert).

A device is considered stale when it hasn't reported for
upload_interval_seconds * DEVICE_OFFLINE_GRACE_MULTIPLIER.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.database.session import AsyncSessionLocal
from app.models.device import Device
from app.services.alert import alert_service

logger = structlog.get_logger(__name__)


async def mark_stale_devices_offline(db: AsyncSession, now: datetime | None = None) -> int:
    """
    Flip stale ONLINE devices to OFFLINE and raise DEVICE_OFFLINE alerts.
    Returns the number of devices transitioned. Does not commit.
    """
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(Device).where(
            Device.status == "ONLINE",
            Device.last_seen_at.is_not(None)
        # Refresh instances already in the session's identity map, so the
        # sweep never acts on stale attribute values.
        ).execution_options(populate_existing=True)
    )
    transitioned = 0
    for device in result.scalars():
        threshold = timedelta(
            seconds=device.upload_interval_seconds * settings.DEVICE_OFFLINE_GRACE_MULTIPLIER
        )
        if now - device.last_seen_at < threshold:
            continue

        device.status = "OFFLINE"
        await alert_service.create_offline_alert(db, device)
        transitioned += 1
        logger.warning(
            "Device marked offline",
            action="DEVICE_OFFLINE",
            device_uid=device.device_uid,
            last_seen_at=device.last_seen_at.isoformat(),
            threshold_seconds=threshold.total_seconds()
        )
    return transitioned


async def offline_watchdog_loop() -> None:
    """Background loop started from the app lifespan."""
    logger.info(
        "Offline watchdog started",
        interval_seconds=settings.OFFLINE_WATCHDOG_INTERVAL_SECONDS,
        grace_multiplier=settings.DEVICE_OFFLINE_GRACE_MULTIPLIER
    )
    while True:
        try:
            async with AsyncSessionLocal() as db:
                count = await mark_stale_devices_offline(db)
                if count:
                    await db.commit()
        except asyncio.CancelledError:
            logger.info("Offline watchdog stopped")
            raise
        except Exception:
            # Never let a transient DB error kill the watchdog.
            logger.exception("Offline watchdog sweep failed")
        await asyncio.sleep(settings.OFFLINE_WATCHDOG_INTERVAL_SECONDS)
