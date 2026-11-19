from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

web_root = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=web_root), name="student-assets")


@app.get("/", include_in_schema=False)
async def student_app():
    return FileResponse(web_root / "index.html")
