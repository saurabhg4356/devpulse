"""Date and time utilities for DevPulse."""

from datetime import datetime, timezone
from typing import Optional, Union


def parse_iso_datetime(date_str: str) -> datetime:
    """Parse an ISO 8601 string or Git date string into a timezone-aware UTC datetime.
    
    Supports formats:
    - 2026-10-05T14:30:00+00:00
    - 2026-10-05 14:30:00 +0000
    - 2026-10-05T14:30:00Z
    - 2026-10-05
    """
    if not date_str:
        raise ValueError("Cannot parse empty date string")
    
    cleaned = date_str.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        # Fallback to dateutil-style or common git log patterns
        for fmt in (
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%a %b %d %H:%M:%S %Y %z",
        ):
            try:
                dt = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unable to parse datetime string: {date_str}")

    # Standardize to timezone-aware UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def format_iso_datetime(dt: Optional[datetime]) -> str:
    """Format datetime object into standard ISO string."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_display_date(dt: Optional[datetime]) -> str:
    """Format datetime for user-facing terminal outputs."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def days_between(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> int:
    """Calculate the number of calendar days between two datetimes."""
    if start_dt is None or end_dt is None:
        return 0
    delta = abs(end_dt - start_dt)
    return max(0, delta.days)
