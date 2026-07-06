from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.database.session import get_db
from app.schemas.alert import AlertListRead, AlertRead
from app.schemas.common import Page
from app.services.alert import alert_service
from app.api.deps import get_current_user, require_admin, scope_customer_id
from app.models.user import User

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get(
    "",
    response_model=Page[AlertListRead],
    summary="Search Alerts"
)
async def list_alerts(
    q: Optional[str] = Query(None, description="Search term for device name, UID, customer, or type"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE or RESOLVED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins only see alerts for their own devices
    customer_id = scope_customer_id(current_user, None)
    skip = (page - 1) * page_size
    items, total = await alert_service.search_alerts(
        db, q, status, skip, page_size, sort, order, customer_id=customer_id
    )
    
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1
    )

@router.put(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an active alert"
)
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    alert = await alert_service.resolve_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
