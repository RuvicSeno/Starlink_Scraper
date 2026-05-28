"""
FastAPI application entry point.
Sets up CORS, static file serving, route modules, and database lifecycle.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.database import db
from backend.routes import data, scraper

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Startup: ensure directories and connect to database
    settings.ensure_directories()
    await db.connect()
    logger.info("Starlink Scraper API started.")
    logger.info(f"Dashboard: http://{settings.HOST}:{settings.PORT}")

    yield

    # Shutdown: close database
    await db.close()
    logger.info("Starlink Scraper API shut down.")


# Create FastAPI application
app = FastAPI(
    title="Starlink Usage Scraper",
    description="Scrapes Starlink account usage data and presents it in an interactive dashboard.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow local frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API route modules
app.include_router(data.router)
app.include_router(scraper.router)

# Serve frontend static files (CSS, JS, etc.)
frontend_dir = settings.FRONTEND_DIR
if frontend_dir.exists():
    app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
    app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found. Place index.html in /frontend directory."}


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    record_count = await db.get_record_count()
    return {
        "status": "ok",
        "records": record_count,
        "database": str(settings.DATABASE_PATH)
    }
