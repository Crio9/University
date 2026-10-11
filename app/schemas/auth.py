from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    role: Literal["student", "teacher", "staff"]


class LoginRequest(BaseModel):
    email: str
    password: str
