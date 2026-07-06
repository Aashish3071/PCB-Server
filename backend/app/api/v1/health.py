from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc, func
from app.database.session import get_db
from app.models.telemetry import Telemetry
from app.models.device import Device
from app.models.alert import Alert
from app.api.deps import require_admin
from app.core.settings import settings
from app.utils.rate_limit import telemetry_rate_limiter

router = APIRouter()

@router.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Operational health check endpoint.
    """
    # 1. Check DB
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
        
    # 2. Get last telemetry timestamp
    last_telemetry = None
    try:
        stmt = select(Telemetry.timestamp).order_by(desc(Telemetry.timestamp)).limit(1)
        res = await db.execute(stmt)
        last_t = res.scalar_one_or_none()
        if last_t:
            last_telemetry = last_t.isoformat()
    except Exception:
        pass

    return {
        "backend_status": "ok",
        "database_status": db_status,
        "last_telemetry_received": last_telemetry,
        "api_version": "1.0",
        "frontend_version": "1.0"
    }


@router.get("/diagnostics", tags=["System"], dependencies=[Depends(require_admin)])
async def diagnostics(db: AsyncSession = Depends(get_db)):
    """
    Admin-only operational snapshot for the device fleet.

    Answers the questions you'll ask when something looks off:
      - Are devices reporting? (fleet_by_status, last_telemetry_received)
      - Is the rate limiter tripping? (rate_limiter.tracked_devices/recent_hits)
      - What's the retention pipeline sitting on? (row counts)
      - What thresholds are active? (config echo)
    """
    fleet_by_status = {}
    result = await db.execute(select(Device.status, func.count()).group_by(Device.status))
    for status_value, count in result.all():
        fleet_by_status[status_value] = count

    telemetry_rows = (await db.execute(select(func.count()).select_from(Telemetry))).scalar_one()
    open_alerts = (await db.execute(
        select(func.count()).select_from(Alert).where(Alert.is_resolved.is_(False))
    )).scalar_one()

    last_telemetry_row = await db.execute(
        select(Telemetry.timestamp).order_by(desc(Telemetry.timestamp)).limit(1)
    )
    last_telemetry = last_telemetry_row.scalar_one_or_none()

    tracked_devices, recent_hits = await telemetry_rate_limiter.snapshot()

    return {
        "environment": settings.ENVIRONMENT,
        "fleet_by_status": fleet_by_status,
        "telemetry_rows": telemetry_rows,
        "open_alerts": open_alerts,
        "last_telemetry_received": last_telemetry.isoformat() if last_telemetry else None,
        "rate_limiter": {
            "tracked_devices": tracked_devices,
            "recent_hits": recent_hits,
            "burst_limit": telemetry_rate_limiter.burst_limit,
            "burst_window_seconds": telemetry_rate_limiter.burst_window_seconds,
            "floor_multiplier": telemetry_rate_limiter.floor_multiplier
        },
        "config": {
            "device_offline_grace_multiplier": settings.DEVICE_OFFLINE_GRACE_MULTIPLIER,
            "offline_watchdog_interval_seconds": settings.OFFLINE_WATCHDOG_INTERVAL_SECONDS,
            "telemetry_retention_days": settings.TELEMETRY_RETENTION_DAYS,
            "alert_retention_days": settings.ALERT_RETENTION_DAYS,
            "retention_sweep_interval_seconds": settings.RETENTION_SWEEP_INTERVAL_SECONDS,
            "alert_low_battery_pct": settings.ALERT_LOW_BATTERY_PCT,
            "alert_high_temp_c": settings.ALERT_HIGH_TEMP_C,
            "alert_low_voltage_v": settings.ALERT_LOW_VOLTAGE_V
        }
    }
