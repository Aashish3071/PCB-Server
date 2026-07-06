from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.session import get_db
from app.repositories.device import device_repo
from app.models.device import Device
from app.utils.security import verify_password
from app.core.context import get_request_id
from app.core.settings import settings
from app.models.user import User
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import uuid
from sqlalchemy import select

logger = structlog.get_logger(__name__)

security = HTTPBearer()

def get_jwks_client():
    url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(url)

jwks_client = get_jwks_client()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            # Asymmetric only. Supabase's JWKS signing keys are ES256/RS256;
            # allowing the symmetric HS256 alongside a public key from JWKS
            # opens an algorithm-confusion attack surface.
            algorithms=["RS256", "ES256"],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=settings.SUPABASE_URL + "/auth/v1",
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True
            }
        )
            
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            
        user_id = uuid.UUID(user_id_str)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found in database")
            
        return user
        
    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for write/administrative operations: rejects non-admin users."""
    if current_user.role != "admin":
        logger.warning(
            "Authorization failed: admin role required",
            action="RBAC_DENIED",
            user_id=str(current_user.id),
            role=current_user.role,
            request_id=get_request_id()
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


def scope_customer_id(current_user: User, requested_customer_id: uuid.UUID | None) -> uuid.UUID | None:
    """
    Data-isolation helper for list/read endpoints.

    Admins: pass the requested filter through unchanged.
    Customers: always constrained to their own customer_id; requesting another
    customer's data is rejected.
    """
    if current_user.role == "admin":
        return requested_customer_id
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No customer is assigned to this account"
        )
    if requested_customer_id and requested_customer_id != current_user.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return current_user.customer_id


async def get_accessible_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Device:
    """
    Resolves a device by path param and enforces customer isolation.
    Returns 404 (not 403) for cross-tenant access so device existence is not leaked.
    """
    device = await device_repo.get(db, device_id)
    if not device or (
        current_user.role != "admin" and device.customer_id != current_user.customer_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def authenticate_device(
    x_device_uid: str = Header(..., description="Device unique hardware identifier"),
    x_api_key: str = Header(..., description="Device secret API key"),
    db: AsyncSession = Depends(get_db)
):
    device = await device_repo.get_by_uid(db, device_uid=x_device_uid)
    
    if not device:
        logger.warning(
            "Authentication failed: Unknown device UID",
            action="DEVICE_AUTH_FAILURE",
            reason="unknown_uid",
            device_uid=x_device_uid,
            request_id=get_request_id()
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    if not verify_password(x_api_key, device.api_key_hash):
        logger.warning(
            "Authentication failed: Invalid API key",
            action="DEVICE_AUTH_FAILURE",
            reason="invalid_key",
            device_uid=x_device_uid,
            request_id=get_request_id()
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    if device.status == "DISABLED":
        logger.warning(
            "Authentication failed: Device is disabled",
            action="DEVICE_AUTH_FAILURE",
            reason="device_disabled",
            device_uid=x_device_uid,
            request_id=get_request_id()
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device is disabled")
        
    return device


async def check_rate_limit(device: Device = Depends(authenticate_device)):
    """
    Enforces per-device rate limits on telemetry ingest (in-memory sliding window).
    See app.utils.rate_limit for the algorithm and its scaling caveats.
    """
    from fastapi import Response
    from app.utils.rate_limit import telemetry_rate_limiter

    decision = await telemetry_rate_limiter.check(
        device.device_uid, device.upload_interval_seconds
    )
    if not decision.allowed:
        logger.warning(
            "Telemetry rate limit exceeded",
            action="RATE_LIMIT_REJECTED",
            device_uid=device.device_uid,
            retry_after_seconds=decision.retry_after_seconds,
            request_id=get_request_id()
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)}
        )
    return device
