"""
Clock abstraction for time operations.
Allows faking time in tests.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Clock(ABC):
    """Abstract clock interface."""
    
    @abstractmethod
    def now(self) -> datetime:
        """Get current UTC datetime."""
        pass
    
    def now_unix(self) -> int:
        """Get current time as Unix timestamp."""
        return int(self.now().timestamp())


class SystemClock(Clock):
    """Real system clock implementation."""
    
    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)


class FakeClock(Clock):
    """
    Fake clock for testing.
    Time can be set and advanced manually.
    """
    
    def __init__(self, initial: datetime = None):
        if initial is None:
            initial = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        self._current = initial
    
    def now(self) -> datetime:
        return self._current
    
    def set(self, dt: datetime) -> None:
        """Set current time."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        self._current = dt
    
    def advance_seconds(self, seconds: int) -> None:
        """Advance time by seconds."""
        from datetime import timedelta
        self._current += timedelta(seconds=seconds)
    
    def advance_minutes(self, minutes: int) -> None:
        """Advance time by minutes."""
        self.advance_seconds(minutes * 60)
    
    def advance_hours(self, hours: int) -> None:
        """Advance time by hours."""
        self.advance_seconds(hours * 3600)
    
    def advance_days(self, days: int) -> None:
        """Advance time by days."""
        self.advance_seconds(days * 86400)
