from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.profiles import router as profiles_router

app = FastAPI(title="University Auth Mock")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(profiles_router, prefix="/api/v1")