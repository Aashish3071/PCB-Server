from fastapi import APIRouter, Depends, Header, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import structlog

from app.database.session import get_db
from app.models.device import Device
from app.schemas.telemetry import TelemetryIngest, TelemetryResponse, FleetTelemetryRead
from app.api.deps import check_rate_limit, get_current_user, scope_customer_id
from app.models.user import User
from app.services.telemetry import telemetry_service
from app.schemas.common import Page
from uuid import UUID
import math

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

@router.post(
    "",
    response_model=TelemetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest telemetry from a device",
    description="Securely receive telemetry from deployed devices. Validates payload, implements idempotency, and updates device state."
)
async def ingest_telemetry(
    payload: TelemetryIngest,
    device: Device = Depends(check_rate_limit),
    x_telemetry_version: str = Header(default="1", description="Protocol version (defaults to 1)"),
    db: AsyncSession = Depends(get_db)
):
    logger.info("Received telemetry", device_uid=device.device_uid, version=x_telemetry_version)
    
    # Ingest telemetry logic (handles duplicate insertion idempotency gracefully)
    inserted = await telemetry_service.ingest_telemetry(db, device, payload)
    
    # We explicitly commit the transaction here to finalize insertion & state updates
    if inserted:
        await db.commit()
    
    return TelemetryResponse(
        status="accepted",
        server_time=datetime.now(timezone.utc),
        # Server->device control channel: per-device configurable interval.
        next_upload_seconds=device.upload_interval_seconds
    )

@router.get(
    "",
    response_model=Page[FleetTelemetryRead],
    summary="List fleet telemetry"
)
async def list_fleet_telemetry(
    device_id: UUID = Query(None),
    customer_id: UUID = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins are always scoped to their own customer_id
    customer_id = scope_customer_id(current_user, customer_id)
    skip = (page - 1) * page_size
    items, total = await telemetry_service.search_fleet_telemetry(
        db, device_id, customer_id, start_date, end_date, skip, page_size
    )
    
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1
    )

@router.get(
    "/export",
    summary="Export fleet telemetry to JSON"
)
async def export_fleet_telemetry(
    device_id: UUID = Query(None),
    customer_id: UUID = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins are always scoped to their own customer_id
    customer_id = scope_customer_id(current_user, customer_id)
    export_data = await telemetry_service.export_fleet_telemetry(
        db, device_id, customer_id, start_date, end_date
    )
    return export_data
