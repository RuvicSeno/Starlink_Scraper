"""
Data extraction module.
Intercepts network API responses from the Starlink dashboard to capture
usage data in JSON format. Falls back to DOM scraping if needed.
"""

import logging
import re
from pathlib import Path
import json
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import Page, Response
from backend.config import settings

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts usage data from Starlink dashboard via network interception."""

    def __init__(self):
        self.captured_responses: list[dict] = []
        self.usage_records: list[dict] = []
        self.debug_stats: dict = {}
        self._reset_debug_stats()

    def _reset_debug_stats(self) -> None:
        self.debug_stats = {
            "responses_seen": 0,
            "responses_captured": 0,
            "response_status_counts": {},
            "sample_relevant_urls": [],
            "sample_response_shapes": [],
            "selector_counts": {},
            "parse_attempts": 0,
            "records_added": 0,
            "dropped_no_date": 0,
            "dropped_bad_date": 0,
            "dropped_zero_values": 0,
            "dropped_duplicate_date": 0,
            "dom_lines_count": 0,
            "dom_gb_matches": 0,
            "dom_date_matches": 0,
            "dom_records_added": 0,
            "captured_count_before_parse": 0,
            "records_before_filter": 0,
            "captured_payload_samples": [],
            "focused_payload_samples": []
        }

    def _setup_response_listener(self, page: Page) -> None:
        """Attach a network response listener to capture usage API data."""
        async def handle_response(response: Response):
            url = response.url
            content_type = response.headers.get("content-type", "").lower()
            self.debug_stats["responses_seen"] += 1
            # Capture responses that look like usage/billing data endpoints
            usage_patterns = [
                "usage", "data-usage", "billing-cycle",
                "consumption", "service-line", "telemetry",
                "graphql", "api", "residential data", "total data usage"
            ]
            looks_relevant = any(p in url.lower() for p in usage_patterns)
            is_json_response = "json" in content_type or "graphql-response" in content_type
            if looks_relevant and is_json_response:
                try:
                    body = await response.json()
                    self.debug_stats["responses_captured"] += 1
                    status_key = str(response.status)
                    self.debug_stats["response_status_counts"][status_key] = (
                        self.debug_stats["response_status_counts"].get(status_key, 0) + 1
                    )
                    if len(self.debug_stats["sample_relevant_urls"]) < 20:
                        self.debug_stats["sample_relevant_urls"].append(url)
                    if len(self.debug_stats["sample_response_shapes"]) < 20:
                        shape = list(body.keys())[:10] if isinstance(body, dict) else f"list[{len(body)}]" if isinstance(body, list) else type(body).__name__
                        self.debug_stats["sample_response_shapes"].append({
                            "url": url,
                            "status": response.status,
                            "shape": shape
                        })
                    url_l = url.lower()
                    if any(k in url_l for k in ["telemetryagg", "data-usage", "annotated", "residential data", "total data usage"]):
                        if len(self.debug_stats["focused_payload_samples"]) < 5:
                            if isinstance(body, dict):
                                sample = json.dumps(body, default=str)[:5000]
                            elif isinstance(body, list):
                                sample = json.dumps(body[:3], default=str)[:5000]
                            else:
                                sample = str(body)[:5000]
                            self.debug_stats["focused_payload_samples"].append({
                                "url": url,
                                "status": response.status,
                                "content_type": content_type,
                                "sample": sample
                            })
                    self.captured_responses.append({
                        "url": url,
                        "status": response.status,
                        "content_type": content_type,
                        "data": body
                    })
                    logger.info("Captured relevant API response: %s (%s)", url, response.status)
                except Exception:
                    pass  # Not all responses are JSON

        page.on("response", handle_response)

    async def extract_usage_from_page(self, page: Page) -> list[dict]:
        """
        Extract data via network interception from the current view.
        Tries to parse captured data, falling back to DOM if needed.
        """
        # Keep network debug context collected since listener attachment.
        # Only reset parse-specific counters for this extraction pass.
        self.debug_stats.update({
            "parse_attempts": 0,
            "records_added": 0,
            "dropped_no_date": 0,
            "dropped_bad_date": 0,
            "dropped_zero_values": 0,
            "dropped_duplicate_date": 0,
            "dom_lines_count": 0,
            "dom_gb_matches": 0,
            "dom_date_matches": 0,
            "dom_records_added": 0,
            "captured_count_before_parse": 0,
            "records_before_filter": 0
        })
        # Clear only previous usage_records, keep captured_responses as they contain the data we want!
        self.usage_records.clear()

        # Try scrolling to trigger lazy-loaded content
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        captured_count = len(self.captured_responses)
        self.debug_stats["captured_count_before_parse"] = captured_count

        # Basic raw content verification
        body_text = await page.inner_text("body")
        html = await page.content()
        logger.info("Page raw content: url=%s html_len=%s body_text_len=%s", page.url, len(html), len(body_text.strip()))
        if len(body_text.strip()) > 0:
            logger.info("Body text sample: %s", body_text.strip().replace("\n", " ")[:400])
        else:
            logger.warning("Body text is empty. This page is likely rendered client-side via JavaScript.")

        if settings.SCRAPER_DEBUG:
            snapshot_path = Path(settings.DEBUG_DIR) / "last_page_snapshot.html"
            snapshot_path.write_text(html, encoding="utf-8")
            logger.info("Saved HTML snapshot to %s", snapshot_path)

        # Parse captured API responses
        for resp in self.captured_responses[:10]:
            if len(self.debug_stats["captured_payload_samples"]) < 10:
                data = resp.get("data")
                sample = None
                if isinstance(data, dict):
                    sample = json.dumps(data, default=str)[:1400]
                elif isinstance(data, list):
                    sample = json.dumps(data[:2], default=str)[:1400]
                self.debug_stats["captured_payload_samples"].append({
                    "url": resp.get("url"),
                    "status": resp.get("status"),
                    "content_type": resp.get("content_type"),
                    "sample": sample
                })
        for resp in self.captured_responses:
            self._parse_api_response(resp["data"])
        self.debug_stats["records_before_filter"] = len(self.usage_records)

        # Clear captured responses so we don't re-process them next month
        self.captured_responses.clear()

        # If network interception didn't yield results, try DOM scraping
        if not self.usage_records:
            if captured_count == 0:
                logger.warning("No relevant JSON API responses captured; trying DOM extraction.")
            else:
                logger.warning(
                    "Captured %s relevant API response(s) but parsed 0 records; "
                    "response schema likely changed.",
                    captured_count
                )
            await self._extract_from_dom(page)

        self._log_debug_summary()
        logger.info(f"Extracted {len(self.usage_records)} usage records from current view.")
        return self.usage_records

    def _parse_api_response(self, data: dict | list) -> None:
        """
        Parse a captured API JSON response and extract usage records.
        Handles various possible response structures from Starlink's API.
        """
        if self._parse_annotated_billing_usage(data):
            return
        self._walk_and_parse_records(data)

    def _parse_annotated_billing_usage(self, data: dict | list) -> bool:
        """
        Parse Starlink telemetry annotated usage payload:
        content.billingCyclesAnnotated[].dailyData
        """
        if not isinstance(data, dict):
            return False

        content = data.get("content")
        if not isinstance(content, dict):
            return False

        billing_cycles = content.get("billingCyclesAnnotated")
        if not isinstance(billing_cycles, list) or not billing_cycles:
            return False

        parsed_any = False
        for cycle in billing_cycles:
            if not isinstance(cycle, dict):
                continue

            start_date_str = cycle.get("startDate")
            if not start_date_str:
                continue

            normalized_start = self._normalize_date(start_date_str)
            if not normalized_start:
                continue

            try:
                start_dt = datetime.strptime(normalized_start, "%Y-%m-%d")
            except ValueError:
                continue

            daily_data = cycle.get("dailyData")
            if not isinstance(daily_data, list):
                continue

            for day_index, day_values in enumerate(daily_data):
                day_total = 0.0
                if isinstance(day_values, list):
                    numeric_values = [v for v in day_values if isinstance(v, (int, float))]
                    day_total = float(sum(numeric_values))
                elif isinstance(day_values, (int, float)):
                    day_total = float(day_values)
                else:
                    continue

                day_date = (start_dt + timedelta(days=day_index)).strftime("%Y-%m-%d")
                record = {
                    "date": day_date,
                    # This endpoint exposes residential daily usage totals.
                    "residential_gb": round(day_total, 4),
                    "total_gb": round(day_total, 4),
                    "month": (start_dt + timedelta(days=day_index)).strftime("%Y-%m"),
                    "year": (start_dt + timedelta(days=day_index)).year
                }

                existing_dates = {r["date"] for r in self.usage_records}
                if record["date"] not in existing_dates:
                    self.usage_records.append(record)
                    self.debug_stats["records_added"] += 1
                else:
                    self.debug_stats["dropped_duplicate_date"] += 1
                parsed_any = True

        if parsed_any:
            logger.info("Parsed %s records from billingCyclesAnnotated payload.", self.debug_stats["records_added"])
        return parsed_any

    def _walk_and_parse_records(self, value: dict | list) -> None:
        """Recursively walk nested JSON objects and parse usage-like records."""
        if isinstance(value, list):
            for item in value:
                self._walk_and_parse_records(item)
            return

        if not isinstance(value, dict):
            return

        self._parse_single_record(value)

        # GraphQL payloads are commonly nested under `data` with arbitrary depth.
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                self._walk_and_parse_records(nested)

    def _parse_single_record(self, item: dict) -> None:
        """Parse a single usage data item into a normalized record."""
        if not isinstance(item, dict):
            return

        self.debug_stats["parse_attempts"] += 1
        record = {}

        # Extract date — try various field names
        date_val = None
        for key in ["date", "startDate", "start_date", "day",
                     "timestamp", "billingDate", "usageDate"]:
            if key in item:
                date_val = item[key]
                break

        if not date_val:
            self.debug_stats["dropped_no_date"] += 1
            return  # Can't use a record without a date

        # Normalize date to YYYY-MM-DD
        record["date"] = self._normalize_date(date_val)
        if not record["date"]:
            self.debug_stats["dropped_bad_date"] += 1
            return

        # Extract total usage first.
        total_gb = self._extract_gb(item, [
            "total", "totalBytes", "total_bytes",
            "totalUsage", "dataUsage", "usageBytes"
        ])
        if total_gb == 0:
            down_gb = self._extract_gb(item, [
                "download", "downloadBytes", "download_bytes",
                "downlinkBytes", "rx_bytes", "rxBytes"
            ])
            up_gb = self._extract_gb(item, [
                "upload", "uploadBytes", "upload_bytes",
                "uplinkBytes", "tx_bytes", "txBytes"
            ])
            total_gb = down_gb + up_gb
        record["total_gb"] = total_gb
        record["residential_gb"] = self._extract_gb(item, [
            "standard", "standardBytes", "standard_bytes",
            "standardData", "basicBytes", "deprioritizedBytes",
            "residential", "residentialBytes", "residentialData"
        ])
        if record["residential_gb"] == 0 and total_gb > 0:
            record["residential_gb"] = total_gb

        # Derive month and year from date
        try:
            dt = datetime.strptime(record["date"], "%Y-%m-%d")
            record["month"] = dt.strftime("%Y-%m")
            record["year"] = dt.year
        except ValueError:
            return

        # Only add records that have meaningful data
        if record["total_gb"] > 0 or record["residential_gb"] > 0:
            # Avoid duplicates
            existing_dates = {r["date"] for r in self.usage_records}
            if record["date"] not in existing_dates:
                self.usage_records.append(record)
                self.debug_stats["records_added"] += 1
            else:
                self.debug_stats["dropped_duplicate_date"] += 1
        else:
            self.debug_stats["dropped_zero_values"] += 1

    def _extract_gb(self, item: dict, keys: list[str]) -> float:
        """Extract a data value from item, converting bytes to GB if needed."""
        for key in keys:
            if key in item:
                val = item[key]
                if isinstance(val, str):
                    try:
                        val = float(val.replace(",", "").strip())
                    except ValueError:
                        continue
                if isinstance(val, (int, float)):
                    # Heuristic: if value > 1_000_000, assume it's in bytes
                    if val > 1_000_000:
                        return round(val / (1024 ** 3), 4)  # Bytes to GB
                    elif val > 1_000:
                        return round(val / (1024 ** 2), 4)  # KB to GB
                    else:
                        return round(val, 4)  # Already in GB
        return 0.0

    def _normalize_date(self, date_val) -> Optional[str]:
        """Convert various date formats to YYYY-MM-DD."""
        if isinstance(date_val, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            try:
                ts = date_val / 1000 if date_val > 1e12 else date_val
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                return None

        if isinstance(date_val, str):
            # Try common date formats
            for fmt in [
                "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z",
                "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"
            ]:
                try:
                    return datetime.strptime(date_val[:26], fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            # Try ISO format parsing as fallback
            try:
                return datetime.fromisoformat(date_val.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except ValueError:
                pass

        return None

    async def _extract_from_dom(self, page: Page) -> None:
        """
        Fallback: extract usage data directly from the DOM using raw text parsing.
        This avoids fragile CSS selectors by analyzing the logical flow of text on the screen.
        If a GB value is found, it looks at the surrounding lines for a date.
        """
        try:
            body_text = await page.inner_text("body", timeout=5000)
            lines = [l.strip() for l in body_text.split("\n") if l.strip()]
            self.debug_stats["dom_lines_count"] = len(lines)

            selector_probe = [
                "[class*='usage']",
                "[data-testid*='usage']",
                "[class*='billing']",
                "[data-testid*='billing']",
                "table",
                "canvas"
            ]
            for selector in selector_probe:
                count = await page.locator(selector).count()
                self.debug_stats["selector_counts"][selector] = count
                logger.info("Selector '%s' matched %s element(s).", selector, count)
            
            for i, line in enumerate(lines):
                # Is this line a GB value? (e.g., "15.2 GB", "3 GB", "12.5GB")
                data_match = re.search(r'^([\d.]+)\s*(?:GB|gb)$', line)
                if not data_match:
                     data_match = re.search(r'([\d.]+)\s*(?:GB|gb)', line)
                     
                if data_match:
                    self.debug_stats["dom_gb_matches"] += 1
                    val = float(data_match.group(1))
                    
                    # Avoid parsing the total monthly limit (e.g. "1000 GB") if it's too suspiciously round
                    # But we'll accept it if it pairs with a very specific daily date.
                    
                    # Look for a date in the surrounding +/- 4 lines
                    start_idx = max(0, i - 4)
                    end_idx = min(len(lines), i + 5)
                    
                    found_date = None
                    for j in range(start_idx, end_idx):
                        date_match = re.search(
                            r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|'
                            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})',
                            lines[j]
                        )
                        if date_match:
                            found_date = self._normalize_date(date_match.group())
                            if found_date:
                                self.debug_stats["dom_date_matches"] += 1
                                break
                                
                    if found_date:
                        record = {
                            "date": found_date,
                            "residential_gb": val,
                            "total_gb": val,
                        }
                        
                        dt = datetime.strptime(found_date, "%Y-%m-%d")
                        record["month"] = dt.strftime("%Y-%m")
                        record["year"] = dt.year
                        
                        existing_dates = {r["date"] for r in self.usage_records}
                        if record["date"] not in existing_dates:
                            self.usage_records.append(record)
                            self.debug_stats["dom_records_added"] += 1

        except Exception as e:
            logger.warning(f"DOM extraction failed: {e}")

    def _log_debug_summary(self) -> None:
        logger.info(
            "Extraction debug summary: %s",
            json.dumps(self.debug_stats, default=str)
        )
        if settings.SCRAPER_DEBUG:
            debug_path = Path(settings.DEBUG_DIR) / "last_extraction_debug.json"
            debug_path.write_text(json.dumps(self.debug_stats, indent=2, default=str), encoding="utf-8")
            logger.info("Saved extraction debug summary to %s", debug_path)


async def navigate_months(page: Page) -> list[str]:
    """
    Detect available months on the Starlink usage page and return
    the navigation strategy. Looks for month selector / navigation buttons.
    """
    available_months = []

    try:
        # Look for month navigation elements
        month_selectors = [
            "[class*='month-selector']", "[class*='date-picker']",
            "[class*='period-selector']", "[data-testid*='month']",
            "select[class*='month']", "[class*='billing-period']",
            "button[aria-label*='previous']", "button[aria-label*='month']"
        ]

        for selector in month_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                for el in elements:
                    text = await el.inner_text()
                    if text.strip():
                        available_months.append(text.strip())
                break

        # Try to find month options in dropdowns
        options = await page.query_selector_all("option")
        for opt in options:
            text = await opt.inner_text()
            month_match = re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}|\d{4}-\d{2})',
                text
            )
            if month_match:
                available_months.append(month_match.group())

    except Exception as e:
        logger.warning(f"Error detecting months: {e}")

    logger.info(f"Found {len(available_months)} month navigation elements.")
    return available_months
