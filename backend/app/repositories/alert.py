from uuid import UUID
from typing import Optional, Any
from sqlalchemy import select, desc, asc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.alert import Alert
from app.models.device import Device
from app.models.customer import Customer
from app.repositories.base import BaseRepository

class AlertRepository(BaseRepository[Alert, Any, Any]):
    async def get_recent_alerts(self, db: AsyncSession, device_id: UUID, limit: int = 5):
        stmt = select(Alert).where(
            Alert.device_id == device_id
        ).order_by(
            Alert.is_resolved.asc(),
            desc(Alert.created_at)
        ).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def search_alerts(
        self,
        db: AsyncSession,
        query_str: Optional[str] = None,
        status_filter: Optional[str] = None, # "ACTIVE" or "RESOLVED"
        customer_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
        sort: str = "created_at",
        order: str = "desc"
    ):
        query = select(Alert, Device.device_name, Device.device_uid, Customer.company_name).select_from(Alert)\
            .join(Device, Alert.device_id == Device.id)\
            .outerjoin(Customer, Device.customer_id == Customer.id)

        count_query = select(func.count()).select_from(Alert)\
            .join(Device, Alert.device_id == Device.id)\
            .outerjoin(Customer, Device.customer_id == Customer.id)

        if customer_id:
            # Data-isolation scoping: restrict to alerts on the customer's own devices
            query = query.filter(Device.customer_id == customer_id)
            count_query = count_query.filter(Device.customer_id == customer_id)

        if query_str:
            search_cond = or_(
                Device.device_name.ilike(f"%{query_str}%"),
                Device.device_uid.ilike(f"%{query_str}%"),
                Customer.company_name.ilike(f"%{query_str}%"),
                Alert.alert_type.ilike(f"%{query_str}%")
            )
            query = query.filter(search_cond)
            count_query = count_query.filter(search_cond)
            
        if status_filter == "ACTIVE":
            query = query.filter(Alert.is_resolved == False)
            count_query = count_query.filter(Alert.is_resolved == False)
        elif status_filter == "RESOLVED":
            query = query.filter(Alert.is_resolved == True)
            count_query = count_query.filter(Alert.is_resolved == True)
            
        if sort == "device_name":
            order_col = Device.device_name
        elif sort == "created_at":
            order_col = Alert.created_at
        else:
            order_col = Alert.created_at
            
        order_by = desc(order_col) if order == "desc" else asc(order_col)
        
        query = query.order_by(order_by).offset(skip).limit(limit)
        
        results = await db.execute(query)
        total = await db.execute(count_query)
        
        return results.all(), total.scalar_one()

alert_repo = AlertRepository(Alert)
