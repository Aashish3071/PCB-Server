from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from uuid import UUID

from app.database.session import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, CurrentUser
from app.core.settings import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["users"])

def get_permissions(role: str) -> list[str]:
    if role == "admin":
        return [
            "devices:read", "devices:write", "devices:delete",
            "customers:read", "customers:write", "customers:delete",
            "telemetry:read", "alerts:read", "alerts:write",
            "users:read", "users:write"
        ]
    elif role == "customer":
        return [
            "devices:read",
            "telemetry:read",
            "alerts:read"
        ]
    return []

@router.get("/me", response_model=CurrentUser)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's profile and permissions."""
    return CurrentUser(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        customer_id=current_user.customer_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        permissions=get_permissions(current_user.role)
    )

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user. Performs Supabase Auth creation + local DB synchronization."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase configuration missing")
        
    try:
        from supabase import create_client
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        
        # 1. Create Supabase Auth User
        auth_response = supabase.auth.admin.create_user({
            "email": user_in.email,
            "password": user_in.password,
            "email_confirm": True
        })
        
        # auth_response.user contains the newly created user
        supabase_user = auth_response.user
        
        if not supabase_user:
            raise HTTPException(status_code=500, detail="Failed to create Supabase user")
            
        # 2. Create local DB User
        db_user = User(
            id=UUID(supabase_user.id),
            email=user_in.email,
            role=user_in.role,
            customer_id=user_in.customer_id,
            is_active=True
        )
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
        logger.info("User created successfully", admin_id=str(current_user.id), new_user_id=str(db_user.id))
        return db_user
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error server-side, but don't leak internals to the client.
        logger.error("Failed to create user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create user. The email may already be in use."
        )
