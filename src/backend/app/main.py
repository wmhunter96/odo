from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import settings
from .db import SessionLocal, init_db
from .routes import charts, fillups, importexport, ocr, settings as settings_routes, stats, vehicles
from .seed import seed_defaults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("odo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    logger.info("Odo backend started (data dir: %s)", settings.data_dir)
    yield
    logger.info("Odo backend shutting down")


app = FastAPI(title="Odo", version=__version__, lifespan=lifespan)

app.include_router(vehicles.router)
app.include_router(fillups.router)
app.include_router(ocr.router)
app.include_router(stats.router)
app.include_router(charts.router)
app.include_router(importexport.router)
app.include_router(settings_routes.router)


@app.get("/api/healthz")
def healthz():
    return JSONResponse(
        {
            "status": "ok",
            "version": __version__,
            "git_sha": settings.git_sha,
            "build_date": settings.build_date,
        }
    )


# --- Static frontend (PWA build) ---------------------------------------
# The production image copies the built Vite app to app/static. In local
# dev without a build present, the API still runs fine on its own -- only
# the SPA fallback route below is skipped.
if settings.static_dir.exists():
    assets_dir = settings.static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = settings.static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = settings.static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Not found"}, status_code=404)
