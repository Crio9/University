"""Explicit operator-only bootstrap and privilege management (DB access required).

Never invoke from application startup or public HTTP endpoints.
"""
import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, engine
from app.models.profile import StaffProfile
from app.models.user import User


async def bootstrap_admin(db: AsyncSession, *, email: str, password: str) -> None:
    if len(password) < 12:
        raise ValueError("Bootstrap admin password must be at least 12 characters")
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Invalid email")
    async with db.begin():
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise ValueError("Account already exists; bootstrap will not promote it")
        db.add(User(
            email=email,
            full_name="System administrator",
            password_hash=hash_password(password),
            role="admin",
        ))


async def grant_role(db: AsyncSession, *, email: str, role: str) -> None:
    if role not in {"staff", "admin"}:
        raise ValueError("Only privileged staff/admin role grants are supported")
    async with db.begin():
        user = await db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise ValueError("Existing account required for role grant")
        # Existing student/teacher profile rows are preserved; the active role changes.
        user.role = role
        if role == "staff" and await db.get(StaffProfile, user.id) is None:
            db.add(StaffProfile(user_id=user.id))


async def run(args):
    async with AsyncSessionLocal() as db:
        if args.command == "bootstrap-admin":
            password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
            if not password:
                raise ValueError("Set ADMIN_BOOTSTRAP_PASSWORD in the operator environment")
            await bootstrap_admin(db, email=args.email, password=password)
        else:
            await grant_role(db, email=args.email, role=args.role)
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Manage privileged roles explicitly")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap-admin")
    bootstrap.add_argument("--email", required=True)
    grant = commands.add_parser("grant")
    grant.add_argument("--email", required=True)
    grant.add_argument("--role", required=True, choices=["staff", "admin"])
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
