"""
utils/timezone_utils.py - IST (Asia/Kolkata) timezone helpers.

All persisted timestamps are UTC-aware datetimes.
This module centralises the conversions so no other module
needs to import pytz directly.
"""
from __future__ import annotations

from datetime import datetime, date, time

import pytz

IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.utc


# -- Basic converters ----------------------------------------------------------

def now_ist() -> datetime:
    """Return the current IST-aware datetime."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(UTC)


def to_ist(dt: datetime) -> datetime:
    """Convert any aware datetime to IST."""
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    return dt.astimezone(IST)


def to_utc(dt: datetime) -> datetime:
    """Convert any aware datetime to UTC."""
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.astimezone(UTC)


# -- Date helpers --------------------------------------------------------------

def today_ist() -> date:
    """Return today's date in IST."""
    return now_ist().date()


def today_ist_str() -> str:
    """Return today's date in IST as YYYY-MM-DD string."""
    return today_ist().strftime("%Y-%m-%d")


def date_to_doc_id(d: date | str) -> str:
    """Convert a date (or YYYY-MM-DD string) to compact YYYYMMDD format."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return d.strftime("%Y%m%d")


def doc_id_to_date(doc_id: str) -> date:
    """Convert YYYYMMDD doc-id back to a date object."""
    return datetime.strptime(doc_id, "%Y%m%d").date()


# -- Timestamp formatting -------------------------------------------------------

def format_ist(dt: datetime | None, fmt: str = "%d %b %Y, %I:%M %p") -> str:
    """
    Return a human-readable IST string.

    Parameters
    ----------
    dt  : Datetime to format.  Returns '' if None.
    fmt : strftime format.  Default produces  "04 Mar 2025, 10:30 AM".
    """
    if dt is None:
        return ""
    return to_ist(dt).strftime(fmt)


def format_time_hhmm(t: str) -> str:
    """
    Convert a stored 24-hr "HH:MM" string to 12-hr display  "10:00 AM".
    Returns the original string on parse error.
    """
    try:
        parsed = datetime.strptime(t, "%H:%M")
        return parsed.strftime("%I:%M %p")
    except (ValueError, TypeError):
        return t or ""


# -- Duration helpers ----------------------------------------------------------

def duration_minutes(start: datetime, end: datetime) -> int:
    """Return elapsed whole minutes between two aware datetimes."""
    delta = end - start
    return max(0, int(delta.total_seconds() // 60))


def minutes_to_hhmm(minutes: int) -> str:
    """Convert minutes to 'Xh Ym' string  (e.g.  125 -> '2h 5m')."""
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m"


# -- Period boundaries (for analytics) ----------------------------------------

def period_range(period: str) -> tuple[date, date]:
    """
    Return (start_date, end_date) for a named period relative to today IST.

    Supported periods: daily, weekly, monthly, quarterly, yearly.
    """
    today = today_ist()

    if period == "daily":
        return today, today

    if period == "weekly":
        from datetime import timedelta
        start = today - timedelta(days=today.weekday())
        return start, today

    if period == "monthly":
        start = today.replace(day=1)
        return start, today

    if period == "quarterly":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1)
        return start, today

    if period == "yearly":
        start = today.replace(month=1, day=1)
        return start, today

    raise ValueError(f"Unknown period: {period!r}. "
                     "Use: daily, weekly, monthly, quarterly, yearly")
