"""
Base Command class for CQRS write operations.
Commands have side effects and may publish events.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Dict, Any
import logging

from infrastructure.event_bus import EventBus
from infrastructure.clock import Clock
from infrastructure.cache import Cache

T = TypeVar('T')


class BaseCommand(ABC, Generic[T]):
    """
    Base class for all Commands (write operations).
    
    Commands:
    - Have side effects (create, update, delete)
    - May publish events
    - Should be idempotent when possible
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        clock: Clock,
        cache: Optional[Cache] = None,
        logger: Optional[logging.Logger] = None
    ):
        self._event_bus = event_bus
        self._clock = clock
        self._cache = cache
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, **kwargs) -> T:
        """
        Execute the command.
        Must be implemented by subclasses.
        """
        pass
    
    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publish domain event with graceful degradation.
        
        Event publishing failures are logged but do NOT fail the command.
        Core business logic (like saving report data) must succeed
        even if the event bus is temporarily unavailable.
        
        Automatically adds timestamp as Unix timestamp.
        """
        payload['timestamp'] = self._clock.now_unix()
        try:
            self._event_bus.publish(event_type, payload)
        except Exception as e:
            self._logger.error(
                f"Failed to publish event {event_type}: {e}. "
                f"Event will be lost but command continues.",
                extra={'event_type': event_type, 'payload': payload}
            )
    
    def invalidate_cache(self, key: str) -> None:
        """Invalidate a cache key."""
        if self._cache:
            self._cache.delete(key)
    
    def log_info(self, message: str, **extra) -> None:
        """Log info message with extra fields."""
        self._logger.info(message, extra=extra)
    
    def log_warning(self, message: str, **extra) -> None:
        """Log warning message with extra fields."""
        self._logger.warning(message, extra=extra)
    
    def log_error(self, message: str, **extra) -> None:
        """Log error message with extra fields."""
        self._logger.error(message, extra=extra)
