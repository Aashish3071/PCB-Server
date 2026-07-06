from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.customer import customer_repo
from app.repositories.device import device_repo
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.models.customer import Customer

class CustomerService:
    @staticmethod
    async def get_customer(db: AsyncSession, id: UUID) -> Customer:
        customer = await customer_repo.get(db, id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer

    @staticmethod
    async def create_customer(db: AsyncSession, obj_in: CustomerCreate) -> Customer:
        return await customer_repo.create(db, obj_in=obj_in)

    @staticmethod
    async def update_customer(db: AsyncSession, id: UUID, obj_in: CustomerUpdate) -> Customer:
        customer = await CustomerService.get_customer(db, id)
        return await customer_repo.update(db, db_obj=customer, obj_in=obj_in)

    @staticmethod
    async def delete_customer(db: AsyncSession, id: UUID) -> Customer:
        customer = await CustomerService.get_customer(db, id)
        
        # Prevent deletion if devices exist
        devices = await device_repo.get_by_customer(db, id)
        if devices:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete customer with assigned devices."
            )
            
        return await customer_repo.remove(db, id=id)

customer_service = CustomerService()
