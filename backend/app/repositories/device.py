from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, or_, func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.models.customer import Customer
from app.models.telemetry import Telemetry

class DeviceRepository(BaseRepository[Device, DeviceCreate, DeviceUpdate]):
    async def get_by_uid(self, db: AsyncSession, device_uid: str) -> Optional[Device]:
        result = await db.execute(select(self.model).filter(self.model.device_uid == device_uid))
        return result.scalars().first()
        
    async def get_latest_device_uid_number(self, db: AsyncSession) -> int:
        """Helper to get the highest sequential number for new device UID generation."""
        # This will extract the numeric part of SLRMS-000001
        # In a high concurrency environment, we would use a sequence.
        # But since provisioning is an admin task, this is sufficient for MVP.
        query = select(self.model.device_uid).order_by(desc(self.model.device_uid)).limit(1)
        result = await db.execute(query)
        latest_uid = result.scalar_one_or_none()
        
        if not latest_uid or not latest_uid.startswith("SLRMS-"):
            return 0
            
        try:
            return int(latest_uid.split("-")[1])
        except (ValueError, IndexError):
            return 0

    async def search(
        self, 
        db: AsyncSession, 
        *, 
        query_str: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[List[Device], int]:
        
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        filters = []
        if customer_id:
            filters.append(self.model.customer_id == customer_id)
        if status:
            filters.append(self.model.status == status)
            
        if query_str:
            # Join customer to search by customer name
            query = query.join(Customer)
            count_query = count_query.join(Customer)
            
            search_filter = or_(
                self.model.device_uid.ilike(f"%{query_str}%"),
                self.model.device_name.ilike(f"%{query_str}%"),
                Customer.company_name.ilike(f"%{query_str}%")
            )
            filters.append(search_filter)
            
        if filters:
            query = query.filter(*filters)
            count_query = count_query.filter(*filters)
            
        order_col = getattr(self.model, sort, getattr(self.model, "created_at"))
        order_by = desc(order_col) if order.lower() == "desc" else asc(order_col)
        
        query = query.order_by(order_by).offset(skip).limit(limit)
        
        results = await db.execute(query)
        total = await db.execute(count_query)
        
        return results.scalars().all(), total.scalar_one()

    async def search_detailed(
        self, 
        db: AsyncSession, 
        *, 
        query_str: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[List[tuple], int]:
        
        # Subquery for latest telemetry per device
        latest_telemetry_subq = (
            select(
                Telemetry.device_id,
                Telemetry.battery_percentage,
                Telemetry.signal_strength
            )
            .distinct(Telemetry.device_id)
            .order_by(Telemetry.device_id, desc(Telemetry.timestamp))
            .subquery()
        )

        query = select(
            self.model, 
            Customer.company_name, 
            latest_telemetry_subq.c.battery_percentage, 
            latest_telemetry_subq.c.signal_strength
        ).join(Customer, self.model.customer_id == Customer.id) \
         .outerjoin(latest_telemetry_subq, self.model.id == latest_telemetry_subq.c.device_id)

        count_query = select(func.count()).select_from(self.model)

        filters = []
        if customer_id:
            filters.append(self.model.customer_id == customer_id)
        if status:
            filters.append(self.model.status == status)
            
        if query_str:
            # We already joined customer in the main query, but count_query needs it too for filtering
            count_query = count_query.join(Customer)
            
            search_filter = or_(
                self.model.device_uid.ilike(f"%{query_str}%"),
                self.model.device_name.ilike(f"%{query_str}%"),
                Customer.company_name.ilike(f"%{query_str}%")
            )
            filters.append(search_filter)
            
        if filters:
            query = query.filter(*filters)
            count_query = count_query.filter(*filters)
            
        order_col = getattr(self.model, sort, getattr(self.model, "created_at"))
        order_by = desc(order_col) if order.lower() == "desc" else asc(order_col)
        
        query = query.order_by(order_by).offset(skip).limit(limit)
        
        results = await db.execute(query)
        total = await db.execute(count_query)
        
        return results.all(), total.scalar_one()

    async def get_by_customer(self, db: AsyncSession, customer_id: UUID) -> List[Device]:
        result = await db.execute(select(self.model).filter(self.model.customer_id == customer_id))
        return result.scalars().all()

device_repo = DeviceRepository(Device)
