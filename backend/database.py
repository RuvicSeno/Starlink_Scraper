"""
SQLite database module with async operations via aiosqlite.
Handles table creation, CRUD operations, and query helpers.
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from backend.config import settings

logger = logging.getLogger(__name__)

# SQL statements for table creation
CREATE_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS usage_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    residential_gb REAL NOT NULL DEFAULT 0.0,
    month TEXT NOT NULL,
    year INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_SCRAPE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    months_scraped INTEGER DEFAULT 0,
    records_saved INTEGER DEFAULT 0,
    error_message TEXT
);
"""

# Create index on month for fast filtering
CREATE_MONTH_INDEX = """
CREATE INDEX IF NOT EXISTS idx_usage_month ON usage_data(month);
"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or settings.DATABASE_PATH)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection and create tables if needed."""
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrent read performance
        await self._db.execute("PRAGMA journal_mode=WAL;")

        # Create tables
        await self._db.execute(CREATE_USAGE_TABLE)
        await self._ensure_usage_schema()
        await self._db.execute(CREATE_SCRAPE_LOG_TABLE)
        await self._db.execute(CREATE_MONTH_INDEX)
        await self._db.commit()

        logger.info(f"Database connected: {self.db_path}")

    async def _ensure_usage_schema(self) -> None:
        """
        Ensure usage_data has the current column set.
        Keeps backward compatibility with old DB files.
        """
        cursor = await self._db.execute("PRAGMA table_info(usage_data)")
        columns = [row["name"] for row in await cursor.fetchall()]
        column_set = set(columns)
        target_columns = {"id", "date", "residential_gb", "month", "year", "created_at"}

        # Rebuild table if legacy columns (including total_gb) are present.
        if column_set != target_columns:
            value_candidates = []
            if "residential_gb" in column_set:
                value_candidates.append("NULLIF(residential_gb, 0)")
            if "standard_gb" in column_set:
                value_candidates.append("NULLIF(standard_gb, 0)")
            if "total_gb" in column_set:
                value_candidates.append("NULLIF(total_gb, 0)")
            if "download_gb" in column_set and "upload_gb" in column_set:
                value_candidates.append("NULLIF(COALESCE(download_gb, 0) + COALESCE(upload_gb, 0), 0)")

            residential_expr = "COALESCE(" + ", ".join(value_candidates + ["0"]) + ")"
            created_expr = "created_at" if "created_at" in column_set else "datetime('now')"

            await self._db.execute(
                """
                CREATE TABLE usage_data_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    residential_gb REAL NOT NULL DEFAULT 0.0,
                    month TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            await self._db.execute(
                f"""
                INSERT INTO usage_data_new (id, date, residential_gb, month, year, created_at)
                SELECT id, date, {residential_expr}, month, year, {created_expr}
                FROM usage_data;
                """
            )
            await self._db.execute("DROP TABLE usage_data;")
            await self._db.execute("ALTER TABLE usage_data_new RENAME TO usage_data;")
            logger.info("Migrated usage_data schema to residential-only columns.")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed.")

    # ── Usage Data CRUD ───────────────────────────────────────────────

    async def upsert_usage(self, record: dict) -> None:
        """
        Insert or update a daily usage record.
        Uses date as the unique key — re-scraping the same date updates values.
        """
        await self._db.execute(
            """
            INSERT INTO usage_data (date, residential_gb, month, year)
            VALUES (:date, :residential_gb, :month, :year)
            ON CONFLICT(date) DO UPDATE SET
                residential_gb = :residential_gb,
                created_at = datetime('now')
            """,
            record
        )
        await self._db.commit()

    async def upsert_usage_batch(self, records: list[dict]) -> int:
        """Insert or update multiple usage records in a single transaction."""
        if not records:
            logger.warning("upsert_usage_batch called with 0 records.")
            return 0

        logger.info("Persisting %s record(s) to database.", len(records))
        await self._db.executemany(
            """
            INSERT INTO usage_data (date, residential_gb, month, year)
            VALUES (:date, :residential_gb, :month, :year)
            ON CONFLICT(date) DO UPDATE SET
                residential_gb = :residential_gb,
                created_at = datetime('now')
            """,
            records
        )
        await self._db.commit()
        logger.info("Database upsert committed successfully for %s record(s).", len(records))
        return len(records)

    async def get_daily_usage(self, month: Optional[str] = None) -> list[dict]:
        """
        Get daily usage records, optionally filtered by month (YYYY-MM).
        Returns records ordered by date ascending.
        """
        base_query = (
            "SELECT id, date, "
            "residential_gb, month, year, created_at "
            "FROM usage_data"
        )
        if month:
            cursor = await self._db.execute(
                f"{base_query} WHERE month = ? ORDER BY date ASC",
                (month,)
            )
        else:
            cursor = await self._db.execute(
                f"{base_query} ORDER BY date ASC"
            )

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_monthly_usage(self) -> list[dict]:
        """Get aggregated monthly usage statistics."""
        cursor = await self._db.execute(
            """
            SELECT
                month,
                SUM(residential_gb) as residential_gb,
                COUNT(*) as days_with_data,
                ROUND(AVG(residential_gb), 3) as avg_daily_residential_gb,
                date as peak_day,
                MAX(residential_gb) as peak_residential_gb
            FROM usage_data
            GROUP BY month
            ORDER BY month ASC
            """
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            row_dict = dict(row)
            # Get the actual peak day for this month
            peak_cursor = await self._db.execute(
                """
                SELECT date, residential_gb FROM usage_data
                WHERE month = ? ORDER BY residential_gb DESC LIMIT 1
                """,
                (row_dict["month"],)
            )
            peak_row = await peak_cursor.fetchone()
            if peak_row:
                row_dict["peak_day"] = peak_row["date"]
                row_dict["peak_residential_gb"] = peak_row["residential_gb"]
            results.append(row_dict)
        return results

    async def get_usage_summary(self) -> dict:
        """Get overall usage summary for dashboard overview."""
        cursor = await self._db.execute(
            """
            SELECT
                COALESCE(SUM(residential_gb), 0) as total_residential_gb,
                COALESCE(AVG(residential_gb), 0) as avg_daily_residential_gb,
                COUNT(*) as total_days,
                COUNT(DISTINCT month) as months_count
            FROM usage_data
            """
        )
        row = await cursor.fetchone()
        summary = dict(row) if row else {
            "total_residential_gb": 0,
            "avg_daily_residential_gb": 0, "total_days": 0, "months_count": 0
        }

        # Get peak day
        peak_cursor = await self._db.execute(
            "SELECT date, residential_gb FROM usage_data ORDER BY residential_gb DESC LIMIT 1"
        )
        peak_row = await peak_cursor.fetchone()
        if peak_row:
            summary["peak_day"] = peak_row["date"]
            summary["peak_residential_gb"] = peak_row["residential_gb"]
        else:
            summary["peak_day"] = None
            summary["peak_residential_gb"] = None

        # Get latest month and its total
        latest_cursor = await self._db.execute(
            """
            SELECT month, SUM(residential_gb) as month_total
            FROM usage_data
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
            """
        )
        latest_row = await latest_cursor.fetchone()
        if latest_row:
            summary["latest_month"] = latest_row["month"]
            summary["current_month_residential_gb"] = latest_row["month_total"]
        else:
            summary["latest_month"] = None
            summary["current_month_residential_gb"] = None

        return summary

    async def get_available_months(self) -> list[str]:
        """Get list of months that have data."""
        cursor = await self._db.execute(
            "SELECT DISTINCT month FROM usage_data ORDER BY month ASC"
        )
        rows = await cursor.fetchall()
        return [row["month"] for row in rows]

    async def get_record_count(self) -> int:
        """Get total number of usage records."""
        cursor = await self._db.execute("SELECT COUNT(*) as cnt FROM usage_data")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ── Scrape Log CRUD ───────────────────────────────────────────────

    async def create_scrape_log(self) -> int:
        """Create a new scrape log entry and return its ID."""
        cursor = await self._db.execute(
            "INSERT INTO scrape_log (started_at, status) VALUES (?, 'running')",
            (datetime.now().isoformat(),)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def update_scrape_log(self, log_id: int, **kwargs) -> None:
        """Update a scrape log entry with given fields."""
        if not kwargs:
            return
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [log_id]
        await self._db.execute(
            f"UPDATE scrape_log SET {set_clauses} WHERE id = ?",
            values
        )
        await self._db.commit()

    async def get_scrape_history(self, limit: int = 20) -> list[dict]:
        """Get recent scrape log entries."""
        cursor = await self._db.execute(
            "SELECT * FROM scrape_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# Singleton database instance
db = Database()
