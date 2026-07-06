import math
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.api.deps import get_current_user, require_admin, scope_customer_id, get_accessible_device
from app.models.device import Device
from app.models.user import User

from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceRead,
    DeviceProvisioned,
    DeviceStatus,
    DeviceListRead,
    DeviceOverviewResponse
)
from app.schemas.telemetry import TelemetryRead
from app.schemas.common import Page
from app.services.device import device_service
from app.repositories.device import device_repo

router = APIRouter(prefix="/devices", tags=["Devices"])

@router.post(
    "",
    response_model=DeviceProvisioned,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a Device",
    description="Creates a new device for a customer, assigns a unique `device_uid`, and generates a secure API key. Admin only.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "customer_id": "123e4567-e89b-12d3-a456-426614174000",
                        "device_name": "Pole-12",
                        "device_type": "solar_rms"
                    }
                }
            }
        }
    }
)
async def provision_device(
    device_in: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Provisions a new device.

    **CRITICAL**: The `api_key_plaintext` is returned ONLY ONCE in this response.
    It cannot be retrieved later. If lost, the key must be rotated.
    """
    device, plaintext_key = await device_service.provision_device(db, obj_in=device_in)

    response_data = device.__dict__.copy()
    response_data["api_key_plaintext"] = plaintext_key

    return response_data


@router.post(
    "/{device_id}/rotate-key",
    response_model=dict,
    summary="Rotate API Key",
    description="Generates a new API key for the device and invalidates the old one. Admin only."
)
async def rotate_api_key(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Rotates the API key.

    **CRITICAL**: The new `api_key_plaintext` is returned ONLY ONCE in this response.
    """
    new_key = await device_service.rotate_api_key(db, id=device_id)
    return {"message": "API key rotated successfully", "api_key_plaintext": new_key}


@router.get(
    "/by-uid/{device_uid}",
    response_model=DeviceRead,
    summary="Get a Device by UID",
    description="Retrieves the details of a specific device by its physical hardware identifier (`device_uid`)."
)
async def get_device_by_uid(
    device_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = await device_repo.get_by_uid(db, device_uid=device_uid)
    # 404 (not 403) for cross-tenant access so device existence is not leaked
    if not device or (
        current_user.role != "admin" and device.customer_id != current_user.customer_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.get(
    "/{device_id}",
    response_model=DeviceRead,
    summary="Get device by ID"
)
async def get_device(
    device: Device = Depends(get_accessible_device)
):
    return device

@router.get(
    "/{device_id}/overview",
    response_model=DeviceOverviewResponse,
    summary="Get device overview (Details, Analytics, Alerts)"
)
async def get_device_overview(
    device: Device = Depends(get_accessible_device),
    db: AsyncSession = Depends(get_db)
):
    return await device_service.get_device_overview(db, device.id)

@router.get(
    "/{device_id}/telemetry",
    response_model=Page[TelemetryRead],
    summary="Get paginated telemetry history for a device"
)
async def get_device_telemetry(
    device: Device = Depends(get_accessible_device),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    skip = (page - 1) * page_size
    items, total = await device_service.get_device_telemetry(db, device.id, skip, page_size)
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get(
    "/{device_id}/export",
    summary="Export device data as JSON"
)
async def export_device_data(
    device: Device = Depends(get_accessible_device),
    format: str = Query("json", description="Export format (json)"),
    db: AsyncSession = Depends(get_db)
):
    # Note: the user specified JSON export
    data = await device_service.export_device_data(db, device.id)
    return data


@router.put(
    "/{device_id}",
    response_model=DeviceRead,
    summary="Update a Device",
    description="Updates device properties. Can be used to change device status (e.g. MAINTENANCE, DISABLED). Admin only."
)
async def update_device(
    device_id: UUID,
    device_in: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    return await device_service.update_device(db, id=device_id, obj_in=device_in)


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Device",
    description="Permanently deletes a device from the platform. Admin only."
)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    await device_service.delete_device(db, id=device_id)
    return None


@router.get(
    "",
    response_model=Page[DeviceListRead],
    summary="List Devices",
    description="Retrieves a paginated list of devices with telemetry and customer details. Customer users only see their own devices."
)
async def list_devices(
    q: Optional[str] = Query(None, description="Search by device UID, name, or customer name"),
    customer_id: Optional[UUID] = Query(None, description="Filter by Customer ID"),
    status: Optional[DeviceStatus] = Query(None, description="Filter by Device Status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("created_at", description="Field to sort by"),
    order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins are always scoped to their own customer_id
    customer_id = scope_customer_id(current_user, customer_id)
    skip = (page - 1) * page_size
    devices, total = await device_service.search_devices(
        db,
        query_str=q,
        customer_id=customer_id,
        status=status,
        skip=skip,
        limit=page_size,
        sort=sort,
        order=order
    )

    return Page(
        items=devices,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1
    )
