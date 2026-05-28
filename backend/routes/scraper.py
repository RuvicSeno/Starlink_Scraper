"""
Scraper control API routes.
Start, stop, and monitor scraping jobs from the frontend.
"""

import logging
from fastapi import APIRouter

from backend.database import db
from scraper.tasks import scraper_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrape", tags=["scraper"])


@router.post("/start")
async def start_scraping():
    """
    Start a new scraping job in the background.
    Returns immediately with status — poll /status for progress.
    """
    try:
        result = await scraper_manager.start()
        return {"status": "ok", "message": result}
    except Exception as e:
        logger.error(f"Error starting scraper: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def get_scrape_status():
    """Get current scraping status and progress."""
    try:
        status = scraper_manager.get_status()
        return {"status": "ok", "data": status}
    except Exception as e:
        logger.error(f"Error getting scrape status: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/stop")
async def stop_scraping():
    """Cancel a running scraping job."""
    try:
        result = await scraper_manager.stop()
        return {"status": "ok", "message": result}
    except Exception as e:
        logger.error(f"Error stopping scraper: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/history")
async def get_scrape_history():
    """Get past scraping run history."""
    try:
        history = await db.get_scrape_history()
        return {"status": "ok", "data": history}
    except Exception as e:
        logger.error(f"Error fetching scrape history: {e}")
        return {"status": "error", "message": str(e), "data": []}
