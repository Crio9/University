from fastapi import HTTPException, status
from pydantic import BaseModel

from app.mock_store import profiles


def read_profile(current_user: dict) -> dict:
    email = current_user["email"]
    role = current_user["role"]

    return {
        **current_user,
        "profile": profiles[role].get(email, {}),
    }


def update_profile(required_role: str, data: BaseModel, current_user: dict) -> dict:
    if current_user["role"] != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only {required_role} users can update this profile",
        )

    email = current_user["email"]
    profiles[required_role][email] = data.model_dump()

    return {
        "message": f"{required_role.capitalize()} profile updated",
        "profile": profiles[required_role][email],
    }
