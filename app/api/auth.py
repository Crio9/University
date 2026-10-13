from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import Token, UserLogin, UserRead, UserRegister
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)) -> UserRead:
    user = auth_service.register_user(db, data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = auth_service.authenticate_user(
        db, UserLogin(email=form_data.username, password=form_data.password)
    )
    token = auth_service.issue_token_for_user(user)
    return Token(access_token=token)
