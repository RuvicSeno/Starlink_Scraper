"""
Pydantic data models for API request/response serialization
and internal data structures.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UsageRecord(BaseModel):
    """A single day's usage data."""
    id: Optional[int] = None
    date: str                          # YYYY-MM-DD
    residential_gb: float              # Residential data usage in GB
    month: str                         # YYYY-MM for grouping
    year: int                          # Year for grouping
    created_at: Optional[str] = None


class MonthlyUsage(BaseModel):
    """Aggregated monthly usage statistics."""
    month: str                # YYYY-MM
    residential_gb: float
    days_with_data: int
    avg_daily_residential_gb: float
    peak_day: Optional[str] = None
    peak_residential_gb: Optional[float] = None


class UsageSummary(BaseModel):
    """Overall usage summary for the dashboard overview cards."""
    total_residential_gb: float
    avg_daily_residential_gb: float
    peak_day: Optional[str] = None
    peak_residential_gb: Optional[float] = None
    total_days: int
    months_count: int
    latest_month: Optional[str] = None
    current_month_residential_gb: Optional[float] = None


class ScrapeStatus(BaseModel):
    """Current status of the scraping engine."""
    status: str  # "idle", "running", "completed", "error", "auth_required"
    progress: Optional[str] = None      # e.g., "Processing March 2025..."
    months_found: int = 0
    months_scraped: int = 0
    records_saved: int = 0
    started_at: Optional[str] = None
    error: Optional[str] = None


class ScrapeLogEntry(BaseModel):
    """A historical scrape run record."""
    id: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None
    status: str
    months_scraped: int
    records_saved: int
    error_message: Optional[str] = None
