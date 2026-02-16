"""
Datetime utilities for Unix timestamp conversion.
All datetimes in API transit are Unix timestamps (seconds).
"""
from datetime import datetime, timezone
from typing import Optional, Union


def to_unix(dt: Optional[datetime]) -> Optional[int]:
    """
    Convert datetime to Unix timestamp (seconds).
    
    Args:
        dt: datetime object (naive assumed UTC, aware uses its tz)
        
    Returns:
        Unix timestamp in seconds, or None if dt is None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return int(dt.timestamp())


def from_unix(ts: Optional[Union[int, float]]) -> Optional[datetime]:
    """
    Convert Unix timestamp to datetime (UTC).
    
    Args:
        ts: Unix timestamp in seconds
        
    Returns:
        datetime object in UTC, or None if ts is None
    """
    if ts is None:
        return None
    
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def now_unix() -> int:
    """
    Get current time as Unix timestamp.
    
    Returns:
        Current Unix timestamp in seconds
    """
    return int(datetime.now(tz=timezone.utc).timestamp())
