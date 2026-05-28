"""
Playwright browser management.
Handles browser lifecycle, context creation, and session persistence.
"""

import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from backend.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser instances and contexts."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def storage_state_path(self) -> str:
        """Path to the saved session/cookie storage."""
        return str(settings.SESSION_DIR / "storage_state.json")

    @property
    def has_saved_session(self) -> bool:
        """Check if a saved session file exists."""
        return Path(self.storage_state_path).exists()

    async def launch(self, headless: bool = True) -> Page:
        """
        Launch browser and create a page.
        Uses saved session storage if available.
        
        Args:
            headless: Run browser without visible window. Set False for manual login.
        
        Returns:
            Playwright Page instance ready for navigation.
        """
        logger.info(f"Launching browser (headless={headless})...")

        self._playwright = await async_playwright().start()

        # Launch Chromium with reasonable defaults
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )

        # Build context options
        context_options = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "locale": "en-US",
            "timezone_id": "Asia/Manila",
        }

        # Load saved session if it exists
        if self.has_saved_session:
            context_options["storage_state"] = self.storage_state_path
            logger.info("Loaded saved session from storage state.")

        self._context = await self._browser.new_context(**context_options)
        self._page = await self._context.new_page()

        # Stealth: remove webdriver detection flags
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        logger.info("Browser launched successfully.")
        return self._page

    async def save_session(self) -> None:
        """Save current browser session (cookies, localStorage) to disk."""
        if self._context:
            await self._context.storage_state(path=self.storage_state_path)
            logger.info(f"Session saved to {self.storage_state_path}")

    async def close(self) -> None:
        """Gracefully close browser and all resources."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            logger.info("Browser closed.")

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def context(self) -> Optional[BrowserContext]:
        return self._context
