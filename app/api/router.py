from fastapi import APIRouter

from app.api import auth, dictionaries, ingest, posts, profiles

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(posts.router)
api_router.include_router(dictionaries.router)
api_router.include_router(ingest.router)
