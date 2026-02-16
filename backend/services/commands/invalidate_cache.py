"""
Invalidate Cache Command - removes a key from cache.
"""
from .base import BaseCommand


class InvalidateCacheCommand(BaseCommand[bool]):
    """Invalidate کردن کش"""
    
    def execute(self, cache_key: str) -> bool:
        if self._cache:
            self._cache.delete(cache_key)
            self.log_info("Cache invalidated", cache_key=cache_key)
            return True
        return False
