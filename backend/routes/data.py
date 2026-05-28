"""
Data retrieval API routes.
Serves usage data to the frontend dashboard and handles CSV export.
"""

import csv
import io
import logging
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/usage/daily")
async def get_daily_usage(month: Optional[str] = Query(None, description="Filter by month (YYYY-MM)")):
    """
    Get daily usage records.
    Optionally filter by month in YYYY-MM format.
    """
    try:
        records = await db.get_daily_usage(month=month)
        return {"status": "ok", "data": records, "count": len(records)}
    except Exception as e:
        logger.error(f"Error fetching daily usage: {e}")
        return {"status": "error", "message": str(e), "data": [], "count": 0}


@router.get("/usage/monthly")
async def get_monthly_usage():
    """Get aggregated monthly usage statistics."""
    try:
        records = await db.get_monthly_usage()
        residential_total = round(sum(float(r.get("residential_gb") or 0) for r in records), 4)
        logger.info(
            "Monthly usage loaded: months=%s, residential_total=%s",
            len(records),
            residential_total
        )
        return {"status": "ok", "data": records, "count": len(records)}
    except Exception as e:
        logger.error(f"Error fetching monthly usage: {e}")
        return {"status": "error", "message": str(e), "data": [], "count": 0}


@router.get("/usage/all")
async def get_all_usage():
    """Get all usage records for charts and table display."""
    try:
        records = await db.get_daily_usage()
        return {"status": "ok", "data": records, "count": len(records)}
    except Exception as e:
        logger.error(f"Error fetching all usage: {e}")
        return {"status": "error", "message": str(e), "data": [], "count": 0}


@router.get("/usage/summary")
async def get_usage_summary():
    """Get dashboard overview summary statistics."""
    try:
        summary = await db.get_usage_summary()
        months = await db.get_available_months()
        logger.info(
            "Summary loaded: total_residential_gb=%s, months=%s",
            summary.get("total_residential_gb"),
            len(months)
        )
        return {"status": "ok", "data": summary, "available_months": months}
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        return {"status": "error", "message": str(e), "data": {}}


@router.get("/usage/months")
async def get_available_months():
    """Get list of months that have recorded data."""
    try:
        months = await db.get_available_months()
        return {"status": "ok", "data": months}
    except Exception as e:
        logger.error(f"Error fetching months: {e}")
        return {"status": "error", "message": str(e), "data": []}


@router.get("/export/csv")
async def export_csv():
    """
    Export all usage data as a downloadable CSV file.
    Streams the CSV response for memory efficiency.
    """
    try:
        records = await db.get_daily_usage()
        logger.info("CSV export source rows=%s", len(records))

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header row
        writer.writerow([
            "Date", "Residential Data (GB)", "Month", "Year"
        ])

        # Write data rows
        for record in records:
            residential_val = record.get("residential_gb")
            if residential_val is None:
                residential_val = record.get("total_gb", 0)
            writer.writerow([
                record.get("date", ""),
                round(float(residential_val or 0), 4),
                record.get("month", ""),
                record.get("year", ""),
            ])
        logger.info("CSV export completed with residential-first schema.")

        # Reset stream position
        output.seek(0)

        # Return as downloadable CSV
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=starlink_usage_data.csv"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        return {"status": "error", "message": f"Failed to export CSV: {str(e)}"}
