"""
Base Query class for CQRS read operations.
Queries have no side effects and may use caching.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Any
import logging

from infrastructure.cache import Cache
from infrastructure.clock import Clock

T = TypeVar('T')


class BaseQuery(ABC, Generic[T]):
    """
    Base class for all Queries (read operations).
    
    Queries:
    - Have NO side effects
    - May use caching
    - Should be idempotent by nature
    """
    
    def __init__(
        self,
        cache: Optional[Cache] = None,
        clock: Optional[Clock] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs  # Accept extra kwargs for DI compatibility
    ):
        self._cache = cache
        self._clock = clock
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, **kwargs) -> T:
        """
        Execute the query.
        Must be implemented by subclasses.
        """
        pass
    
    def get_cached(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        Returns None if cache is disabled or key not found.
        """
        if self._cache:
            return self._cache.get_json(key)
        return None
    
    def set_cached(self, key: str, value: Any, ttl: int = 3600) -> None:
        """
        Set value in cache.
        No-op if cache is disabled.
        """
        if self._cache:
            self._cache.set_json(key, value, ttl=ttl)
    
    def log_info(self, message: str, **extra) -> None:
        """Log info message with extra fields."""
        self._logger.info(message, extra=extra)
    
    def log_warning(self, message: str, **extra) -> None:
        """Log warning message with extra fields."""
        self._logger.warning(message, extra=extra)
