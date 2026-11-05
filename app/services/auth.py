from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.profile import StudentProfile, TeacherProfile
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> dict:
    email = str(data.email).lower()
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    user = User(
        email=email,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.flush()

    if data.role == "student":
        db.add(StudentProfile(user_id=user.id))
    elif data.role == "teacher":
        db.add(TeacherProfile(user_id=user.id))

    await db.commit()
    return {"message": "User registered"}


async def login_user(db: AsyncSession, data: LoginRequest) -> dict:
    email = str(data.email).lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "message": "You are logged in",
        "result": {
            "access_token": token,
            "token_type": "bearer",
        },
    }
