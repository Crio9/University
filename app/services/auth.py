from fastapi import HTTPException, status

from app.core.security import create_access_token, get_pass_hash, verify_password
from app.mock_store import profiles, users
from app.schemas.auth import LoginRequest, RegisterRequest


def register_user(data: RegisterRequest) -> dict:
    email = str(data.email).lower()
    if email in users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    users[email] = {
        "full_name": data.full_name,
        "role": data.role,
        "password_hash": get_pass_hash(data.password),
    }
    profiles[data.role][email] = {}
    return {"message": "User registered"}


def login_user(data: LoginRequest) -> dict:
    email = str(data.email).lower()
    user = users.get(email)

    if user is None or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "message": "You are logged in",
        "result": {
            "access_token": create_access_token(email),
            "token_type": "bearer",
        },
    }
