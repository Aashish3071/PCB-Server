"""
Bootstrap an administrator account.

Creates (or reuses) the user in Supabase Auth and mirrors it into the local
`users` table with role=admin. Credentials come from the environment:

    ADMIN_EMAIL     (default: admin@pcb.local)
    ADMIN_PASSWORD  (required — no default, must be set)

Run from the backend directory:

    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='a-strong-password' \
        PYTHONPATH=. uv run python scripts/create_admin.py
"""
import asyncio
import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from supabase import Client, create_client

from app.core.settings import settings
from app.database.session import engine
from app.models.user import User
from app.utils.security import get_password_hash


def _already_exists(err: Exception) -> bool:
    msg = str(err).lower()
    return "already" in msg and ("registered" in msg or "exists" in msg)


async def create_admin():
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD

    if not password:
        print(
            "ERROR: ADMIN_PASSWORD is not set. Refusing to create an admin with a "
            "blank/default password.\n"
            "Set it in the environment, e.g.:\n"
            "  ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='...' "
            "PYTHONPATH=. uv run python scripts/create_admin.py"
        )
        sys.exit(1)

    # 1. Provision in Supabase Auth
    supabase: Client = create_client(
        settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
    )
    print(f"Provisioning {email} in Supabase Auth...")
    try:
        response = supabase.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        user_id = uuid.UUID(response.user.id)
        print(f"Supabase user created with ID: {user_id}")
    except Exception as e:
        if _already_exists(e):
            print("User already exists in Supabase. Fetching existing ID...")
            users = supabase.auth.admin.list_users()
            user = next((u for u in users if u.email == email), None)
            if not user:
                print("Could not fetch existing user.")
                sys.exit(1)
            user_id = uuid.UUID(user.id)
        else:
            print(f"Failed to create user in Supabase: {e}")
            sys.exit(1)

    # 2. Provision (or upgrade) in the local database
    print("Provisioning in local database...")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        existing = await session.get(User, user_id)
        if existing:
            existing.role = "admin"
            existing.is_active = True
            existing.hashed_password = get_password_hash(password)
            await session.commit()
            print("Admin user already existed locally — ensured role=admin/active.")
            return

        admin = User(
            id=user_id,
            email=email,
            hashed_password=get_password_hash(password),
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print("Admin user created successfully in local database.")


if __name__ == "__main__":
    asyncio.run(create_admin())
