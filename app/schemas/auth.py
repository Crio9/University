from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    # Privileged roles are assigned only by an operator CLI, never by this endpoint.
    role: Literal["student", "teacher"] = "student"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
