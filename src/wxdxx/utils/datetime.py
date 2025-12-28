"""Datetime parsing and formatting utilities for wxdxx.

This module consolidates all datetime-related parsing and formatting functions
used throughout the application, including:

- Parsing NWS/SPC product timestamps (Zulu time, local time with timezone)
- Parsing ISO 8601 datetime strings from APIs
- Parsing UGC (Universal Geographic Code) header expiry times
- Formatting durations and countdowns for display
"""

import re
from datetime import datetime, timedelta, timezone

# US timezone offsets (hours from UTC)
US_TIMEZONE_OFFSETS: dict[str, int] = {
    # Standard time
    "EST": -5,
    "CST": -6,
    "MST": -7,
    "PST": -8,
    "AKST": -9,
    "HST": -10,
    # Daylight saving time
    "EDT": -4,
    "CDT": -5,
    "MDT": -6,
    "PDT": -7,
    "AKDT": -8,
    # UTC
    "UTC": 0,
    "Z": 0,
}

# Month name abbreviations to numbers
MONTH_NAMES: dict[str, int] = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def parse_zulu_time(
    zulu_str: str, reference_date: datetime | None = None
) -> datetime | None:
    """Parse DDHHMMZ format to datetime.

    Args:
        zulu_str: String in DDHHMMZ format (e.g., "261200" for day 26, 12:00Z)
        reference_date: Reference date for year/month context (defaults to now UTC)

    Returns:
        UTC datetime or None if parsing fails
    """
    if len(zulu_str) != 6:
        return None

    try:
        day = int(zulu_str[0:2])
        hour = int(zulu_str[2:4])
        minute = int(zulu_str[4:6])
    except ValueError:
        return None

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    # Use reference date's year and month
    year = reference_date.year
    month = reference_date.month

    # Handle day rollover (e.g., reference is Dec 31, product valid Jan 1)
    ref_day = reference_date.day
    if day < ref_day - 15:
        # Day is likely next month
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
    elif day > ref_day + 15:
        # Day is likely previous month
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1

    try:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_local_timestamp(text: str) -> datetime | None:
    """Parse local timestamp from NWS/SPC product header.

    Handles formats like:
    - "0412 AM CST THU DEC 25 2025"
    - "505 PM CST THU DEC 18 2025"
    - "1630 UTC THU DEC 25 2025"

    Args:
        text: Product text containing timestamp

    Returns:
        UTC datetime or None if parsing fails
    """
    # Pattern: HHMM AM/PM TZ DAY MON DD YYYY (with optional AM/PM for UTC)
    pattern = r"(\d{3,4})\s*(AM|PM)?\s*(UTC|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST)\s+\w{3}\s+(\w{3})\s+(\d{1,2})\s+(\d{4})"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None

    time_str, ampm, tz_str, month_str, day_str, year_str = match.groups()
    tz_str = tz_str.upper()

    # Parse time
    time_str = time_str.zfill(4)  # Pad to 4 digits (e.g., "505" -> "0505")
    try:
        hour = int(time_str[:-2])
        minute = int(time_str[-2:])
    except ValueError:
        return None

    # Convert 12-hour to 24-hour if AM/PM present
    if ampm:
        ampm = ampm.upper()
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0

    # Parse month
    month = MONTH_NAMES.get(month_str.upper())
    if month is None:
        return None

    try:
        day = int(day_str)
        year = int(year_str)
    except ValueError:
        return None

    # Get timezone offset
    tz_offset = US_TIMEZONE_OFFSETS.get(tz_str, 0)

    try:
        local_tz = timezone(timedelta(hours=tz_offset))
        local_dt = datetime(year, month, day, hour, minute, tzinfo=local_tz)
        return local_dt.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string.

    Handles formats from NWS API like:
    - "2025-12-25T12:00:00Z"
    - "2025-12-25T12:00:00+00:00"
    - "2025-12-25T06:00:00-06:00"

    Args:
        dt_str: ISO datetime string or None

    Returns:
        UTC datetime or None if parsing fails
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_ugc_expiry(text: str) -> datetime | None:
    """Extract expiry datetime from UGC header in product text.

    UGC (Universal Geographic Code) headers contain zone codes and an expiry
    time in DDHHMM format (day of month, hour, minute in UTC).

    Examples:
        CAZ103-104-106-261800-     -> Day 26, 18:00 UTC
        TXZ001-002-003-
        261800-                    -> Day 26, 18:00 UTC (multi-line)

    Args:
        text: Full product text containing UGC header

    Returns:
        Expiry datetime in UTC, or None if parsing fails
    """
    if not text:
        return None

    # UGC expiry is a 6-digit number followed by a dash at end of line
    # It appears in the first few lines of the product
    # Pattern: look for DDHHMM- where DD is day, HH is hour, MM is minute
    match = re.search(r"(\d{6})-\s*$", text[:500], re.MULTILINE)
    if not match:
        return None

    try:
        ddhhmm = match.group(1)
        day = int(ddhhmm[:2])
        hour = int(ddhhmm[2:4])
        minute = int(ddhhmm[4:6])

        # Build datetime using current year/month
        now = datetime.now(timezone.utc)

        # Handle edge case: if we're on day 1-2 and expiry is day 30-31,
        # it's likely from the previous month (product issued end of last month)
        if now.day <= 2 and day >= 28:
            # Roll back to previous month
            if now.month == 1:
                expiry = datetime(
                    now.year - 1, 12, day, hour, minute, 0, tzinfo=timezone.utc
                )
            else:
                # Need to handle months with different day counts
                try:
                    expiry = datetime(
                        now.year,
                        now.month - 1,
                        day,
                        hour,
                        minute,
                        0,
                        tzinfo=timezone.utc,
                    )
                except ValueError:
                    return None  # Day doesn't exist in previous month
        else:
            expiry = now.replace(
                day=day, hour=hour, minute=minute, second=0, microsecond=0
            )

        return expiry
    except (ValueError, IndexError):
        return None


def parse_valid_line(
    text: str, reference_date: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """Parse VALID DDHHMMZ - DDHHMMZ line to extract start and end times.

    Args:
        text: Product text containing VALID line
        reference_date: Reference date for determining year/month (defaults to now)

    Returns:
        Tuple of (valid_start, valid_end) as UTC datetimes, or (None, None) if not found
    """
    match = re.search(r"VALID\s+(\d{6})Z\s*-\s*(\d{6})Z", text, re.IGNORECASE)
    if not match:
        return None, None

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    start_str, end_str = match.group(1), match.group(2)
    start_dt = parse_zulu_time(start_str, reference_date)
    end_dt = parse_zulu_time(end_str, reference_date)

    # Handle case where end day is before start day (crosses month boundary)
    if start_dt and end_dt and end_dt < start_dt:
        # End is in the next month
        if end_dt.month == 12:
            end_dt = end_dt.replace(year=end_dt.year + 1, month=1)
        else:
            end_dt = end_dt.replace(month=end_dt.month + 1)

    return start_dt, end_dt


def format_countdown(seconds: float) -> str:
    """Format remaining time as 'Xh Ym' or 'Xm'.

    Used for displaying countdown timers in sidebar items.

    Args:
        seconds: Number of seconds remaining (must be positive)

    Returns:
        Human-readable countdown string
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string.

    Formats time differences with "ago" suffix for past or "in" prefix for future.
    Resolution is minutes.

    Args:
        seconds: Duration in seconds (positive for past, negative for future)

    Returns:
        Human-readable duration string like "5m ago" or "in 2h 30m"
    """
    abs_seconds = abs(int(seconds))
    hours, remainder = divmod(abs_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if hours > 0:
        time_str = f"{hours}h {minutes}m"
    else:
        time_str = f"{minutes}m"

    if seconds >= 0:
        return f"{time_str} ago"
    return f"in {time_str}"
