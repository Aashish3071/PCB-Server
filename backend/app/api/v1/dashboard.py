from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import structlog
from datetime import datetime

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.device import Device
from app.models.alert import Alert
from app.models.customer import Customer
from app.models.telemetry import Telemetry
from app.schemas.dashboard import DashboardSummary

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["dashboard"])

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get high-level operational metrics for the dashboard. Gated by user role."""
    
    # Base conditions
    device_condition = []
    alert_condition = [Alert.is_resolved == False]
    customer_condition = []
    telemetry_condition = []
    
    if current_user.role == "customer":
        if not current_user.customer_id:
            raise HTTPException(status_code=403, detail="Customer ID not set")
        
        device_condition.append(Device.customer_id == current_user.customer_id)
        
        # Subquery to filter alerts and telemetry by device's customer
        customer_devices_stmt = select(Device.id).where(Device.customer_id == current_user.customer_id)
        
        alert_condition.append(Alert.device_id.in_(customer_devices_stmt))
        telemetry_condition.append(Telemetry.device_id.in_(customer_devices_stmt))
        customer_condition.append(Customer.id == current_user.customer_id)

    try:
        # Total Devices
        stmt_total_dev = select(func.count(Device.id))
        if device_condition:
            stmt_total_dev = stmt_total_dev.where(*device_condition)
        total_devices = (await db.execute(stmt_total_dev)).scalar() or 0

        # Online Devices
        stmt_online_dev = select(func.count(Device.id)).where(Device.status == "ONLINE")
        if device_condition:
            stmt_online_dev = stmt_online_dev.where(*device_condition)
        online_devices = (await db.execute(stmt_online_dev)).scalar() or 0

        # Active Alerts
        stmt_alerts = select(func.count(Alert.id)).where(and_(*alert_condition))
        active_alerts = (await db.execute(stmt_alerts)).scalar() or 0

        # Total Customers
        stmt_customers = select(func.count(Customer.id))
        if customer_condition:
            stmt_customers = stmt_customers.where(*customer_condition)
        total_customers = (await db.execute(stmt_customers)).scalar() or 0
        
        # Last Telemetry Timestamp
        stmt_last_telemetry = select(func.max(Telemetry.server_received_at))
        if telemetry_condition:
            stmt_last_telemetry = stmt_last_telemetry.where(*telemetry_condition)
        last_telemetry_ts = (await db.execute(stmt_last_telemetry)).scalar()

        return DashboardSummary(
            total_devices=total_devices,
            online_devices=online_devices,
            offline_devices=total_devices - online_devices,
            active_alerts=active_alerts,
            total_customers=total_customers,
            last_telemetry_timestamp=last_telemetry_ts
        )

    except Exception as e:
        logger.error("Failed to fetch dashboard summary", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load dashboard metrics")
