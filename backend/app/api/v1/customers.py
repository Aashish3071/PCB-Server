from uuid import UUID
from typing import Optional
import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User

from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerRead, CustomerListRead
from app.schemas.common import Page
from app.services.customer import customer_service
from app.repositories.customer import customer_repo

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.post(
    "", 
    response_model=CustomerRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a Customer",
    description="Creates a new customer organization in the platform."
)
async def create_customer(
    customer_in: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Creates a new customer with the following information:
    - **company_name**: Required. Name of the organization.
    - **contact_person**: Optional.
    - **contact_email**: Optional.
    - **contact_phone**: Optional.
    - **address**: Optional.
    """
    return await customer_service.create_customer(db, obj_in=customer_in)


@router.get(
    "/{customer_id}", 
    response_model=CustomerRead,
    summary="Get a Customer",
    description="Retrieves the details of a specific customer by ID."
)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins may only read their own customer record.
    # 404 (not 403) so other customers' existence is not leaked.
    if current_user.role != "admin" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return await customer_service.get_customer(db, id=customer_id)


@router.put(
    "/{customer_id}", 
    response_model=CustomerRead,
    summary="Update a Customer",
    description="Updates the details of a specific customer."
)
async def update_customer(
    customer_id: UUID,
    customer_in: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    return await customer_service.update_customer(db, id=customer_id, obj_in=customer_in)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Customer",
    description="Deletes a customer. Fails with 409 Conflict if the customer still has assigned devices."
)
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    await customer_service.delete_customer(db, id=customer_id)
    return None


@router.get(
    "", 
    response_model=Page[CustomerListRead],
    summary="List Customers",
    description="Retrieves a paginated list of customers. Can be searched by name or contact details."
)
async def list_customers(
    q: Optional[str] = Query(None, description="Search query string"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("created_at", description="Field to sort by"),
    order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Customer isolation: non-admins only ever see their own customer record
    scoped_id = None
    if current_user.role != "admin":
        if not current_user.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No customer is assigned to this account"
            )
        scoped_id = current_user.customer_id

    skip = (page - 1) * page_size
    rows, total = await customer_repo.search(
        db, query_str=q, customer_id=scoped_id, skip=skip, limit=page_size, sort=sort, order=order
    )
    
    items = []
    for row in rows:
        cust = row[0]
        dev_count = row[1]
        c_dict = cust.__dict__.copy()
        c_dict["device_count"] = dev_count
        items.append(CustomerListRead.model_validate(c_dict))
    
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1
    )
