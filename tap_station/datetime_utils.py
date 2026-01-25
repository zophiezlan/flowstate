"""
Datetime Utilities

This module provides common datetime operations used throughout the application,
ensuring consistent timezone handling and reducing code duplication.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union


def utc_now() -> datetime:
    """
    Get current time in UTC.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """
    Convert datetime to UTC.

    Args:
        dt: Datetime to convert (may be naive or aware)

    Returns:
        Datetime with UTC timezone
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def from_iso(iso_string: str) -> datetime:
    """
    Parse ISO format datetime string.

    Args:
        iso_string: ISO format datetime string

    Returns:
        Parsed datetime (with UTC timezone if naive)
    """
    dt = datetime.fromisoformat(iso_string)
    return to_utc(dt)


def to_iso(dt: datetime) -> str:
    """
    Convert datetime to ISO format string.

    Args:
        dt: Datetime to convert

    Returns:
        ISO format string
    """
    return dt.isoformat()


def minutes_since(timestamp: Union[str, datetime]) -> float:
    """
    Calculate minutes elapsed since a timestamp.

    Args:
        timestamp: ISO string or datetime

    Returns:
        Minutes elapsed (can be negative if timestamp is in future)
    """
    if isinstance(timestamp, str):
        dt = from_iso(timestamp)
    else:
        dt = to_utc(timestamp)

    now = utc_now()
    delta = now - dt
    return delta.total_seconds() / 60


def seconds_since(timestamp: Union[str, datetime]) -> float:
    """
    Calculate seconds elapsed since a timestamp.

    Args:
        timestamp: ISO string or datetime

    Returns:
        Seconds elapsed (can be negative if timestamp is in future)
    """
    if isinstance(timestamp, str):
        dt = from_iso(timestamp)
    else:
        dt = to_utc(timestamp)

    now = utc_now()
    delta = now - dt
    return delta.total_seconds()


def is_within_window(
    timestamp: Union[str, datetime],
    window_minutes: float
) -> bool:
    """
    Check if timestamp is within a time window from now.

    Args:
        timestamp: ISO string or datetime
        window_minutes: Window size in minutes

    Returns:
        True if timestamp is within window
    """
    elapsed = minutes_since(timestamp)
    return 0 <= elapsed <= window_minutes


def is_older_than(
    timestamp: Union[str, datetime],
    threshold_minutes: float
) -> bool:
    """
    Check if timestamp is older than a threshold.

    Args:
        timestamp: ISO string or datetime
        threshold_minutes: Threshold in minutes

    Returns:
        True if timestamp is older than threshold
    """
    return minutes_since(timestamp) > threshold_minutes


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds as a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "5m 30s", "2h 15m", "45s")
    """
    if seconds < 0:
        return "0s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_duration_minutes(minutes: float) -> str:
    """
    Format a duration in minutes as a human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string (e.g., "5 min", "2h 15m")
    """
    if minutes < 0:
        return "0 min"

    if minutes < 60:
        return f"{int(minutes)} min"

    hours = int(minutes // 60)
    mins = int(minutes % 60)

    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def time_ago(timestamp: Union[str, datetime]) -> str:
    """
    Format timestamp as "time ago" string.

    Args:
        timestamp: ISO string or datetime

    Returns:
        Human-readable "time ago" string (e.g., "5 minutes ago", "2 hours ago")
    """
    minutes = minutes_since(timestamp)

    if minutes < 0:
        return "in the future"
    if minutes < 1:
        return "just now"
    if minutes < 60:
        mins = int(minutes)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    if minutes < 1440:  # Less than 24 hours
        hours = int(minutes // 60)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = int(minutes // 1440)
    return f"{days} day{'s' if days != 1 else ''} ago"


def add_minutes(dt: Optional[datetime] = None, minutes: float = 0) -> datetime:
    """
    Add minutes to a datetime.

    Args:
        dt: Base datetime (defaults to now)
        minutes: Minutes to add (can be negative)

    Returns:
        New datetime with minutes added
    """
    if dt is None:
        dt = utc_now()
    return dt + timedelta(minutes=minutes)


def subtract_minutes(dt: Optional[datetime] = None, minutes: float = 0) -> datetime:
    """
    Subtract minutes from a datetime.

    Args:
        dt: Base datetime (defaults to now)
        minutes: Minutes to subtract

    Returns:
        New datetime with minutes subtracted
    """
    return add_minutes(dt, -minutes)


def get_time_window_start(window_minutes: float) -> datetime:
    """
    Get the start of a time window (now - window_minutes).

    Args:
        window_minutes: Window size in minutes

    Returns:
        Datetime at start of window
    """
    return subtract_minutes(utc_now(), window_minutes)


def get_time_window_start_iso(window_minutes: float) -> str:
    """
    Get the start of a time window as ISO string.

    Args:
        window_minutes: Window size in minutes

    Returns:
        ISO format string at start of window
    """
    return to_iso(get_time_window_start(window_minutes))
