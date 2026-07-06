"""
Retention worker: prunes stale telemetry and old resolved alerts.

Deletes are batched so a single sweep never opens a huge transaction on a
Supabase free-tier connection. Set TELEMETRY_RETENTION_DAYS=0 to disable.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.database.session import AsyncSessionLocal
from app.models.alert import Alert
from app.models.telemetry import Telemetry

logger = structlog.get_logger(__name__)


async def _batched_delete(db: AsyncSession, model, cutoff_column, cutoff, extra_filter=None) -> int:
    """Delete rows older than cutoff in RETENTION_BATCH_SIZE chunks. Returns total deleted."""
    total = 0
    while True:
        # Postgres doesn't support LIMIT on DELETE directly; use a subquery.
        subq = select(model.id).where(cutoff_column < cutoff)
        if extra_filter is not None:
            subq = subq.where(extra_filter)
        subq = subq.limit(settings.RETENTION_BATCH_SIZE)

        result = await db.execute(delete(model).where(model.id.in_(subq)))
        deleted = result.rowcount or 0
        total += deleted
        await db.commit()
        if deleted < settings.RETENTION_BATCH_SIZE:
            break
    return total


async def prune_telemetry(db: AsyncSession, now: datetime | None = None) -> int:
    if settings.TELEMETRY_RETENTION_DAYS <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.TELEMETRY_RETENTION_DAYS)
    return await _batched_delete(db, Telemetry, Telemetry.timestamp, cutoff)


async def prune_resolved_alerts(db: AsyncSession, now: datetime | None = None) -> int:
    if settings.ALERT_RETENTION_DAYS <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.ALERT_RETENTION_DAYS)
    return await _batched_delete(
        db, Alert, Alert.resolved_at, cutoff, extra_filter=Alert.is_resolved.is_(True)
    )


async def retention_loop() -> None:
    """Background loop started from the app lifespan."""
    logger.info(
        "Retention worker started",
        telemetry_days=settings.TELEMETRY_RETENTION_DAYS,
        alert_days=settings.ALERT_RETENTION_DAYS,
        sweep_seconds=settings.RETENTION_SWEEP_INTERVAL_SECONDS
    )
    while True:
        try:
            async with AsyncSessionLocal() as db:
                telemetry_pruned = await prune_telemetry(db)
                alerts_pruned = await prune_resolved_alerts(db)
                if telemetry_pruned or alerts_pruned:
                    logger.info(
                        "Retention sweep complete",
                        action="RETENTION_SWEEP",
                        telemetry_pruned=telemetry_pruned,
                        alerts_pruned=alerts_pruned
                    )
        except asyncio.CancelledError:
            logger.info("Retention worker stopped")
            raise
        except Exception:
            logger.exception("Retention sweep failed")
        await asyncio.sleep(settings.RETENTION_SWEEP_INTERVAL_SECONDS)
