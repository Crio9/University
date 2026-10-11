from fastapi import FastAPI, HTTPException
from fastapi import Depends
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)
from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from app.core.security import get_pass_hash, verify_password
from app.core.security import create_access_token, decode_access_token

app = FastAPI()
# Имитируем базу данных
users = {}


profiles = {
    "student": {},
    "teacher": {},
    "staff": {}
}
bearer = HTTPBearer(auto_error=False)

# Pydantic
class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    role: Literal["student", "teacher", "staff"]

class LoginRequest(BaseModel):
    email: str
    password: str

class StudentProfileUpdate(BaseModel):
    university: str
    faculty: str
    course: int = Field(ge=1, le=6)
    study_group: str
    study_program: str
    interest_ids: list[int] = Field(default_factory=list)


class TeacherProfileUpdate(BaseModel):
    department: str
    academic_title: str
    office: str


class StaffProfileUpdate(BaseModel):
    department: str
    position: str

# Functions

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing token"
        )

    token = credentials.credentials

    email = decode_access_token(token)

    if email is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = users.get(email)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return {
        "email": email,
        "full_name": user["full_name"],
        "role": user["role"]
    }

# All requests
@app.post("/api/v1/auth/register")
def register(data: RegisterRequest):
    if data.email in users:
        raise HTTPException(
            status_code=409,
            detail="User already exists"
        )
    users[data.email] = {"full_name":data.full_name,"role":data.role,"password":get_pass_hash(data.password)}
    profiles[data.role][data.email] = {}
    return {"message":"User registered"}
    

@app.post("/api/v1/auth/login")
def login(data: LoginRequest):
    if data.email in users:
        if verify_password(data.password,users[data.email]["password"]) == True:
            return {"message":"You are logged in",
                    "result":{
                        "access_token":create_access_token(data.email),
                        "token_type":"bearer"
                    }}
        
    raise HTTPException(
        status_code=401,
        detail="Unathorized"
    )

@app.get("/api/v1/profile/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):

    email = current_user["email"]
    role = current_user["role"]

    profile = profiles[role].get(email, {})

    return {
        **current_user,
        "profile": profile
    }


@app.put("/api/v1/profile/student")
def update_student(
    data: StudentProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can update this profile"
        )

    email = current_user["email"]

    profiles["student"][email] = data.model_dump()

    return {
        "message": "Student profile updated",
        "profile": profiles["student"][email]
    }


@app.put("/api/v1/profile/teacher")
def update_teacher(
    data: TeacherProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Only teachers can update this profile"
        )

    email = current_user["email"]

    profiles["teacher"][email] = data.model_dump()

    return {
        "message": "Teacher profile updated",
        "profile": profiles["teacher"][email]
    }


@app.put("/api/v1/profile/staff")
def update_staff(
    data: StaffProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "staff":
        raise HTTPException(
            status_code=403,
            detail="Only staff can update this profile"
        )

    email = current_user["email"]

    profiles["staff"][email] = data.model_dump()

    return {
        "message": "Staff profile updated",
        "profile": profiles["staff"][email]
    }
    