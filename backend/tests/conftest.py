import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import uuid
from datetime import datetime, timezone

from app.main import app
from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.base import Base
from app.models.user import User

@pytest.fixture(scope="session")
def postgres_container():
    """Start an ephemeral PostgreSQL container for testing."""
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres

@pytest_asyncio.fixture
async def test_engine(postgres_container):
    """Create async SQLAlchemy engine bound to the test container."""
    from sqlalchemy.pool import NullPool
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    
    # Create all tables (tests skip alembic for speed, just use SQLAlchemy metadata)
    # Wait, we need the sequences. SQLAlchemy Base.metadata.create_all doesn't automatically create sequences
    # created via raw SQL in Alembic. We must create the sequence manually here.
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS device_uid_seq START 1;"))
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def client(test_engine):
    """Provide an async test client with overridden DB dependency."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False,
        autocommit=False, 
        autoflush=False
    )
    
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
            
    app.dependency_overrides[get_db] = override_get_db

    # API tests exercise admin flows: bypass Supabase JWT validation with a
    # fake admin identity. (require_admin resolves through this same override.)
    def override_get_current_user():
        return User(
            id=uuid.uuid4(),
            email="test-admin@test.local",
            role="admin",
            customer_id=None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    app.dependency_overrides[get_current_user] = override_get_current_user

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide a fresh DB session for tests to query DB directly."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_telemetry_rate_limiter():
    """The rate limiter is a module-level singleton; wipe its window between tests."""
    from app.utils.rate_limit import telemetry_rate_limiter
    telemetry_rate_limiter._hits.clear()
    yield
    telemetry_rate_limiter._hits.clear()
