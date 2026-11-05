from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.dictionaries import router as dict_router
from app.api.ingest import router as ingest_router
from app.api.posts import router as posts_router
from app.api.profiles import router as profiles_router
from app.api.telegram_ingest import router as telegram_ingest_router
from app.api.schedule import router as schedule_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(profiles_router)
api_router.include_router(posts_router)
api_router.include_router(dict_router)
api_router.include_router(ingest_router)
api_router.include_router(telegram_ingest_router)
api_router.include_router(schedule_router)
