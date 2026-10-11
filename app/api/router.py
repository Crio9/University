
from fastapi import APIRouter

from app.api.posts import router as posts_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(posts_router)
