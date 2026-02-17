"""
Dependency Injection container and application bootstrap.
"""
from typing import TypeVar, Type, Dict, Any, Optional
import os
import logging

from infrastructure.clock import Clock, SystemClock, FakeClock
from infrastructure.cache import Cache, RedisCache, FakeCache
from infrastructure.event_bus import EventBus, RabbitMQEventBus, FakeEventBus

T = TypeVar('T')

logger = logging.getLogger(__name__)


class Container:
    """
    Simple DI container for managing dependencies.
    Provides both real and fake implementations.
    """
    
    _instance: Optional['Container'] = None
    
    def __init__(self, use_fakes: bool = False):
        self._use_fakes = use_fakes
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Any] = {}
        
        self._register_infrastructure()
    
    def _register_infrastructure(self):
        """Register infrastructure components."""
        if self._use_fakes:
            self._singletons[Clock] = FakeClock()
            self._singletons[Cache] = FakeCache()
            self._singletons[EventBus] = FakeEventBus()
        else:
            self._singletons[Clock] = SystemClock()
            _redis_host = os.environ.get('REDIS_HOST', 'localhost')
            _redis_port = os.environ.get('REDIS_PORT', '6379')
            _redis_password = os.environ.get('REDIS_PASSWORD', '')
            redis_url = os.environ.get('REDIS_URL', f'redis://:{_redis_password}@{_redis_host}:{_redis_port}/0' if _redis_password else f'redis://{_redis_host}:{_redis_port}/0')

            self._singletons[Cache] = RedisCache(redis_url)
            _rabbitmq_host = os.environ.get('RABBITMQ_HOST', 'localhost')
            _rabbitmq_port = os.environ.get('RABBITMQ_PORT', '5672')
            _rabbitmq_user = os.environ.get('RABBITMQ_USER', 'guest')
            _rabbitmq_pass = os.environ.get('RABBITMQ_PASS', 'guest')
            rabbitmq_url = os.environ.get('RABBITMQ_URL', f'amqp://{_rabbitmq_user}:{_rabbitmq_pass}@{_rabbitmq_host}:{_rabbitmq_port}/')
            self._singletons[EventBus] = RabbitMQEventBus(rabbitmq_url)
    
    def get(self, cls: Type[T]) -> T:
        """
        Get instance of a class.
        
        For infrastructure (Clock, Cache, EventBus): returns singleton
        For Commands/Queries: creates new instance with injected dependencies
        """
        if cls in self._singletons:
            return self._singletons[cls]
        
        if cls in self._factories:
            return self._factories[cls](self)
        
        return self._create_service(cls)
    
    def _create_service(self, cls: Type[T]) -> T:
        """Create a service instance with dependencies."""
        clock = self._singletons.get(Clock)
        cache = self._singletons.get(Cache)
        event_bus = self._singletons.get(EventBus)
        
        from services.auth.service import OTPAuthService
        if cls == OTPAuthService:
            return OTPAuthService(cache=cache, event_bus=event_bus)
        
        from services.transcription import TranscriptionService
        if cls == TranscriptionService:
            return TranscriptionService(cache=cache)
        
        from services.media import MediaService
        if cls == MediaService:
            return MediaService(cache=cache)
        
        return cls(
            clock=clock,
            cache=cache,
            event_bus=event_bus,
            logger=logging.getLogger(cls.__name__)
        )
    
    def register_singleton(self, cls: Type[T], instance: T) -> None:
        """Register a singleton instance."""
        self._singletons[cls] = instance
    
    def register_factory(self, cls: Type[T], factory) -> None:
        """Register a factory function."""
        self._factories[cls] = factory
    
    @classmethod
    def instance(cls) -> 'Container':
        """Get or create the global container instance."""
        if cls._instance is None:
            use_fakes = os.environ.get('USE_FAKES', '').lower() in ('true', '1', 'yes')
            cls._instance = cls(use_fakes=use_fakes)
            logger.info(f"Container initialized (use_fakes={use_fakes})")
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the global container (for testing)."""
        cls._instance = None
    
    @classmethod
    def set_instance(cls, container: 'Container') -> None:
        """Set the global container instance (for testing)."""
        cls._instance = container


def get_container() -> Container:
    """Get the global container instance."""
    return Container.instance()


def create_test_container() -> Container:
    """Create a container with fake implementations for testing."""
    return Container(use_fakes=True)
