"""
Authentication and session handling for Starlink account.
Supports manual first login with session persistence for subsequent runs.
"""

import logging
from typing import Optional
from playwright.async_api import Page
from backend.config import settings
from scraper.browser import BrowserManager

logger = logging.getLogger(__name__)

ACCOUNT_URL_PATTERN = "/account"
LOGIN_URL_PATTERN = "/auth"


class AuthManager:
    """Handles Starlink authentication and session validation."""

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager

    async def is_authenticated(self, page: Page) -> bool:
        """Check if the current session is valid by navigating to account page."""
        try:
            logger.info("Checking authentication status...")
            await page.goto(settings.STARLINK_URL, wait_until="commit", timeout=30000)
            
            # Wait a bit for the SPA to render
            await page.wait_for_timeout(5000)
            
            current_url = page.url
            if "auth" in current_url:
                logger.info("Session expired — login required (auth URL detected).")
                return False
                
            # Positive DOM check: verify the dashboard actually rendered text
            try:
                text = await page.inner_text("body", timeout=2000)
                if len(text.strip()) > 150 and "Password" not in text:
                    logger.info("Session is authenticated (dashboard content loaded).")
                    return True
            except Exception:
                pass
                
            logger.info("Session expired — login required (could not verify dashboard content).")
            return False
            
        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            return False

    async def perform_manual_login(self, page: Page) -> bool:
        """Open visible browser for user to log in manually, then save session."""
        logger.info("=" * 60)
        logger.info("MANUAL LOGIN REQUIRED")
        logger.info("A browser window will open. Please log in to your Starlink account.")
        logger.info("=" * 60)
        try:
            # Navigate to the target URL using the provided page
            await page.goto(settings.STARLINK_URL, wait_until="commit", timeout=60000)

            max_wait_seconds = 300
            poll_interval = 2
            
            for _ in range(max_wait_seconds // poll_interval):
                await page.wait_for_timeout(poll_interval * 1000)
                current_url = page.url
                
                # Check if we are on an auth URL
                if "auth" in current_url:
                    continue
                
                # Check if we reached an account URL
                if "/account" in current_url:
                    try:
                        text = await page.inner_text("body", timeout=1000)
                        if len(text.strip()) > 150 and "Password" not in text:
                            logger.info("Login detected (dashboard content loaded)! Saving session...")
                            await page.wait_for_timeout(5000)
                            await self.browser.save_session()
                            return True
                    except Exception:
                        pass
                        
            logger.error("Login timed out after 5 minutes.")
            return False
        except Exception as e:
            logger.error(f"Error during manual login: {e}")
            return False

    async def ensure_authenticated(self, page: Page) -> bool:
        """Ensure valid session using the provided page. Manual login if needed."""
        if self.browser.has_saved_session:
            if await self.is_authenticated(page):
                return True

        # Fallback to manual login
        return await self.perform_manual_login(page)
