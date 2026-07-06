from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, or_, func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.device import Device
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.repositories.base import BaseRepository

class CustomerRepository(BaseRepository[Customer, CustomerCreate, CustomerUpdate]):
    async def search(
        self, 
        db: AsyncSession, 
        *, 
        query_str: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[List[Customer], int]:

        query = select(self.model, func.count(Device.id).label("device_count")).select_from(self.model)\
            .outerjoin(Device, self.model.id == Device.customer_id)\
            .group_by(self.model.id)

        count_query = select(func.count()).select_from(self.model)

        if customer_id:
            # Data-isolation scoping: restrict to a single customer
            query = query.filter(self.model.id == customer_id)
            count_query = count_query.filter(self.model.id == customer_id)

        if query_str:
            search_filter = or_(
                self.model.company_name.ilike(f"%{query_str}%"),
                self.model.contact_person.ilike(f"%{query_str}%"),
                self.model.contact_email.ilike(f"%{query_str}%")
            )
            query = query.filter(search_filter)
            count_query = count_query.filter(search_filter)
            
        order_col = getattr(self.model, sort, getattr(self.model, "created_at"))
        order_by = desc(order_col) if order.lower() == "desc" else asc(order_col)
        
        query = query.order_by(order_by).offset(skip).limit(limit)
        
        results = await db.execute(query)
        total = await db.execute(count_query)
        
        return results.all(), total.scalar_one()

customer_repo = CustomerRepository(Customer)
