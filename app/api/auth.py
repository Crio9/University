from fastapi import APIRouter

from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(data: RegisterRequest):
    return register_user(data)


@router.post("/login")
def login(data: LoginRequest):
    return login_user(data)
