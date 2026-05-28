"""
Async scraping orchestrator.
Manages the full scraping lifecycle: auth → navigate → extract → store.
Provides status tracking and cancellation support.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.config import settings
from backend.database import db
from backend.models import ScrapeStatus
from scraper.browser import BrowserManager
from scraper.auth import AuthManager
from scraper.extractor import DataExtractor, navigate_months

logger = logging.getLogger(__name__)


class ScraperManager:
    """Manages scraping jobs with background execution and status tracking."""

    def __init__(self):
        self._status = ScrapeStatus(status="idle")
        self._task: Optional[asyncio.Task] = None
        self._cancel_event = asyncio.Event()
        self._lock = asyncio.Lock()

    def get_status(self) -> dict:
        """Return current scraping status as a dict."""
        return self._status.model_dump()

    async def start(self) -> str:
        """Start a scraping job. Returns immediately."""
        async with self._lock:
            if self._status.status == "running":
                return "Scraping is already running."

            self._cancel_event.clear()
            self._status = ScrapeStatus(
                status="running",
                progress="Initializing...",
                started_at=datetime.now().isoformat()
            )

            # Run the scraping task in the background
            self._task = asyncio.create_task(self._run_scraping())
            return "Scraping started."

    async def stop(self) -> str:
        """Cancel a running scraping job."""
        if self._status.status != "running":
            return "No scraping job is running."

        self._cancel_event.set()
        self._status.status = "cancelled"
        self._status.progress = "Cancelling..."
        return "Cancellation requested."

    async def _run_scraping(self) -> None:
        """Main scraping workflow executed as a background task."""
        browser = BrowserManager()
        log_id = None

        try:
            # Create scrape log entry
            log_id = await db.create_scrape_log()

            # ── Step 1: Launch Browser & Attach Listener ──
            self._status.progress = "Launching browser..."
            page = await browser.launch(headless=False)

            page.on("console", lambda msg: logger.warning("Browser console [%s]: %s", msg.type, msg.text))
            page.on("requestfailed", lambda req: logger.warning("Request failed: %s | %s", req.url, req.failure))
            
            extractor = DataExtractor()
            extractor._setup_response_listener(page)

            # ── Step 2: Authenticate ──
            self._status.progress = "Authenticating..."
            auth = AuthManager(browser)
            is_valid = await auth.ensure_authenticated(page)

            if not is_valid:
                self._status.status = "auth_required"
                self._status.error = (
                    "Authentication failed. Please restart scraping to "
                    "open the login window."
                )
                if log_id:
                    await db.update_scrape_log(
                        log_id, status="error",
                        error_message="Authentication failed",
                        completed_at=datetime.now().isoformat()
                    )
                return

            if self._cancel_event.is_set():
                return
                
            self._status.progress = "Waiting for dashboard to finish loading..."

            # Ensure extraction runs on the intended service-line usage page.
            if settings.STARLINK_URL not in page.url:
                await page.goto(settings.STARLINK_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Since AuthManager already navigated to the target URL,
            # we just wait patiently for the SPA's background network requests to finish.
            try:
                await page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                pass
                
            # Wait a few extra seconds for React to finish rendering the DOM
            await page.wait_for_timeout(5000)
            logger.info("Pre-extraction page URL: %s", page.url)

            if self._cancel_event.is_set():
                return

            # ── Step 3: Detect available months ──
            self._status.progress = "Detecting available months..."
            available_months = await navigate_months(page)
            self._status.months_found = max(len(available_months), 1)

            # ── Step 4: Extract data ──
            all_records = []
            months_scraped = 0

            if available_months:
                # Navigate through each month
                for i, month_label in enumerate(available_months):
                    if self._cancel_event.is_set():
                        break

                    self._status.progress = f"Scraping {month_label}..."
                    self._status.months_scraped = months_scraped

                    # Try clicking the month selector
                    try:
                        month_elements = await page.query_selector_all(
                            f"text='{month_label}'"
                        )
                        if month_elements:
                            await month_elements[0].click()
                            await page.wait_for_timeout(3000)
                    except Exception as e:
                        logger.warning(f"Could not click month '{month_label}': {e}")

                    # Extract data from current view
                    records = await extractor.extract_usage_from_page(page)
                    all_records.extend(records)
                    months_scraped += 1

                    # Try navigating to previous month via arrow/button
                    await self._try_navigate_previous(page)
            else:
                # No month navigation found — extract from current view
                self._status.progress = "Extracting data from current view..."
                records = await extractor.extract_usage_from_page(page)
                logger.info("Records extracted before aggregation: %s", len(records))
                all_records.extend(records)
                months_scraped = 1

                # Try navigating backwards through months
                max_months = 24  # Try up to 24 months back
                for attempt in range(max_months):
                    if self._cancel_event.is_set():
                        break

                    navigated = await self._try_navigate_previous(page)
                    if not navigated:
                        break

                    self._status.progress = (
                        f"Scraping month {months_scraped + 1}..."
                    )
                    await page.wait_for_timeout(3000)

                    records = await extractor.extract_usage_from_page(page)
                    if not records:
                        break  # No more data available

                    logger.info("Records extracted on month %s: %s", months_scraped + 1, len(records))
                    all_records.extend(records)
                    months_scraped += 1
                    self._status.months_scraped = months_scraped

            if self._cancel_event.is_set():
                self._status.status = "cancelled"
                self._status.progress = "Scraping cancelled by user."
                return

            # ── Step 5: Save to database ──
            self._status.progress = "Saving data to database..."

            # Deduplicate by date
            seen_dates = set()
            unique_records = []
            for r in all_records:
                if r["date"] not in seen_dates:
                    seen_dates.add(r["date"])
                    unique_records.append(r)

            logger.info("Record counts before save: total_extracted=%s unique_by_date=%s", len(all_records), len(unique_records))
            if unique_records:
                logger.info("Sample normalized records: %s", unique_records[:5])

            saved_count = await db.upsert_usage_batch(unique_records)
            logger.info("Record counts after save: saved_count=%s", saved_count)

            # ── Step 6: Complete ──
            self._status.status = "completed"
            self._status.months_scraped = months_scraped
            self._status.records_saved = saved_count
            self._status.progress = (
                f"Done! Saved {saved_count} records across "
                f"{months_scraped} month(s)."
            )

            if log_id:
                await db.update_scrape_log(
                    log_id, status="completed",
                    months_scraped=months_scraped,
                    records_saved=saved_count,
                    completed_at=datetime.now().isoformat()
                )

            logger.info(f"Scraping completed: {saved_count} records saved.")
            # Save the refreshed session
            await browser.save_session()

        except Exception as e:
            logger.error(f"Scraping error: {e}", exc_info=True)
            self._status.status = "error"
            self._status.error = str(e)
            self._status.progress = f"Error: {str(e)}"

            if log_id:
                await db.update_scrape_log(
                    log_id, status="error",
                    error_message=str(e),
                    completed_at=datetime.now().isoformat()
                )
        finally:
            await browser.close()

    async def _try_navigate_previous(self, page) -> bool:
        """Try clicking a 'previous month' navigation button."""
        prev_selectors = [
            "button[aria-label*='previous' i]",
            "button[aria-label*='prev' i]",
            "[class*='prev']",
            "[class*='back']",
            "[data-testid*='prev']",
            "button:has(svg[class*='chevron-left'])",
            "button:has(svg[class*='arrow-left'])",
        ]
        for selector in prev_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    is_disabled = await btn.get_attribute("disabled")
                    if is_disabled:
                        return False
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False


# Singleton instance
scraper_manager = ScraperManager()
