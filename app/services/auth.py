from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.profile import StaffProfile, StudentProfile
from app.models.user import User, UserRole
from app.schemas.auth import UserLogin, UserRegister


def register_user(db: Session, data: UserRegister) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if data.role == UserRole.STUDENT and (not data.faculty or data.course is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student registration requires faculty and course",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.flush()

    if data.role == UserRole.STUDENT:
        db.add(
            StudentProfile(
                user_id=user.id,
                full_name=data.full_name,
                faculty=data.faculty or "",
                course=data.course or 1,
                group_name=data.group_name,
            )
        )
    elif data.role in (UserRole.STAFF, UserRole.ADMIN):
        db.add(
            StaffProfile(
                user_id=user.id,
                full_name=data.full_name,
                department=data.department,
                position=data.position,
            )
        )

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, data: UserLogin) -> User:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


def issue_token_for_user(user: User) -> str:
    return create_access_token(subject=str(user.id))
