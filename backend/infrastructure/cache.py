"""
Cache abstraction for key-value storage.
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
import json


class Cache(ABC):
    """Abstract cache interface."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Get value by key. Returns None if not found or expired."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """Set value with TTL in seconds."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value."""
        value = self.get(key)
        if value is None:
            return None
        return json.loads(value)
    
    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Serialize and set JSON value."""
        self.set(key, json.dumps(value, ensure_ascii=False), ttl=ttl)


class RedisCache(Cache):
    """Redis cache implementation."""
    
    def __init__(self, redis_url: str):
        import redis
        self._client = redis.from_url(redis_url, decode_responses=True)
    
    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)
    
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        self._client.setex(key, ttl, value)
    
    def delete(self, key: str) -> None:
        self._client.delete(key)
    
    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))


class FakeCache(Cache):
    """
    In-memory cache for testing.
    Does not actually expire keys (use FakeClock + manual cleanup for that).
    """
    
    def __init__(self):
        self._store: dict[str, tuple[str, int]] = {}  # key -> (value, expiry_unix)
        self._clock_unix: int = 1705320000  # Fixed time for testing
    
    def get(self, key: str) -> Optional[str]:
        if key not in self._store:
            return None
        
        value, expiry = self._store[key]
        if expiry > 0 and self._clock_unix >= expiry:
            del self._store[key]
            return None
        
        return value
    
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        expiry = self._clock_unix + ttl if ttl > 0 else 0
        self._store[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        self._store.pop(key, None)
    
    def exists(self, key: str) -> bool:
        return self.get(key) is not None
    
    def clear(self) -> None:
        """Clear all keys (for test cleanup)."""
        self._store.clear()
    
    def set_clock(self, unix_ts: int) -> None:
        """Set fake clock for expiry testing."""
        self._clock_unix = unix_ts
    
    def advance_clock(self, seconds: int) -> None:
        """Advance fake clock."""
        self._clock_unix += seconds
