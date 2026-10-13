from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}