"""
Event Bus abstraction for publishing domain events.
Events are consumed by n8n (not subscribed in-app).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)


class EventBus(ABC):
    """Abstract event bus interface (publish only)."""
    
    @abstractmethod
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publish event to the bus.
        
        Args:
            event_type: Event type (e.g., 'user.created', 'report.created')
            payload: Event data (must include 'timestamp' as Unix timestamp)
        """
        pass


class RabbitMQEventBus(EventBus):
    """
    RabbitMQ implementation of event bus.
    
    Features:
    - Thread-safe connection handling
    - Automatic reconnection with exponential backoff
    - Graceful degradation (publish failures don't crash the app)
    - Connection health checks
    """
    
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 0.5  # seconds
    MAX_RETRY_DELAY = 5.0  # seconds
    
    def __init__(self, rabbitmq_url: str, exchange: str = 'peyda_events'):
        import pika
        
        self._url = rabbitmq_url
        self._exchange = exchange
        self._connection = None
        self._channel = None
        self._connection_lock = threading.Lock()
        self._last_connection_attempt = 0
        self._consecutive_failures = 0
        
        # Initialize connection and queue setup immediately
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize connection and queue setup on startup."""
        try:
            with self._connection_lock:
                self._ensure_connection()
        except Exception as e:
            logger.warning(f"Failed to initialize RabbitMQ connection on startup: {e}")
            # Don't raise exception - the connection will be retried on first publish
    
    def _ensure_connection(self) -> bool:
        """
        Ensure connection and channel are established.
        Returns True if connection is ready, False otherwise.
        """
        import pika
        
        need_reconnect = False
        
        try:
            if self._connection is None or self._connection.is_closed:
                need_reconnect = True
            elif self._channel is None or self._channel.is_closed:
                need_reconnect = True
            else:
                # Test the connection with a basic operation
                try:
                    self._connection.process_data_events(time_limit=0)
                except (pika.exceptions.AMQPError,
                        pika.exceptions.ConnectionWrongStateError,
                        AttributeError):
                    need_reconnect = True
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            need_reconnect = True
        
        if not need_reconnect:
            return True
        
        # Close existing connection if any
        self._close_connection_unsafe()
        
        # Create new connection
        try:
            params = pika.URLParameters(self._url)
            params.heartbeat = 180
            params.blocked_connection_timeout = 300
            params.socket_timeout = 10
            
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            
            self._channel.exchange_declare(
                exchange=self._exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Also declare the queue for n8n workflows
            self._channel.queue_declare(
                queue='peyda_events',
                durable=True
            )
            
            # Bind the queue to the exchange with a wildcard routing key to catch all events
            self._channel.queue_bind(
                exchange=self._exchange,
                queue='peyda_events',
                routing_key='#'  # Wildcard to catch all routing keys
            )
            
            self._consecutive_failures = 0
            logger.info("RabbitMQ connection established with peyda_events queue bound to all events")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self._close_connection_unsafe()
            self._consecutive_failures += 1
            return False
    
    def _close_connection_unsafe(self):
        """Close connection without lock (caller must hold lock)."""
        if self._connection:
            try:
                if not self._connection.is_closed:
                    self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._channel = None
    
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publish event with retry logic.
        Raises exception only after all retries fail.
        """
        import pika
        
        last_error = None
        retry_delay = self.INITIAL_RETRY_DELAY
        
        for attempt in range(self.MAX_RETRIES):
            with self._connection_lock:
                try:
                    if not self._ensure_connection():
                        raise ConnectionError("Failed to establish RabbitMQ connection")
                    
                    routing_key = event_type.replace('.', '_')
                    
                    message = json.dumps({
                        'event_type': event_type,
                        'payload': payload
                    }, ensure_ascii=False)
                    
                    self._channel.basic_publish(
                        exchange=self._exchange,
                        routing_key=routing_key,
                        body=message.encode('utf-8'),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # Persistent
                            content_type='application/json'
                        )
                    )
                    
                    logger.info(f"Published event: {event_type}")
                    return  # Success
                    
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Publish attempt {attempt + 1}/{self.MAX_RETRIES} failed for {event_type}: {e}"
                    )
                    self._close_connection_unsafe()
            
            # Wait before retry (outside lock)
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, self.MAX_RETRY_DELAY)
        
        # All retries failed
        logger.error(f"Failed to publish event {event_type} after {self.MAX_RETRIES} attempts: {last_error}")
        raise last_error
    
    def close(self):
        """Close connection."""
        with self._connection_lock:
            self._close_connection_unsafe()
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        with self._connection_lock:
            try:
                if self._connection is None or self._connection.is_closed:
                    return False
                if self._channel is None or self._channel.is_closed:
                    return False
                self._connection.process_data_events(time_limit=0)
                return True
            except Exception:
                return False


class FakeEventBus(EventBus):
    """
    In-memory event bus for testing.
    Stores all published events for assertions.
    """
    
    def __init__(self):
        self._events: List[Dict[str, Any]] = []
    
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        self._events.append({
            'event_type': event_type,
            'payload': payload
        })
    
    @property
    def events(self) -> List[Dict[str, Any]]:
        """Get all published events."""
        return self._events.copy()
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events filtered by type."""
        return [e for e in self._events if e['event_type'] == event_type]
    
    def last_event(self) -> Dict[str, Any] | None:
        """Get the last published event."""
        return self._events[-1] if self._events else None
    
    def clear(self) -> None:
        """Clear all events (for test cleanup)."""
        self._events.clear()
    
    def assert_event_published(self, event_type: str) -> Dict[str, Any]:
        """Assert that an event of given type was published. Returns the event."""
        events = self.get_events_by_type(event_type)
        if not events:
            raise AssertionError(f"No event of type '{event_type}' was published")
        return events[-1]
    
    def assert_no_events(self) -> None:
        """Assert that no events were published."""
        if self._events:
            types = [e['event_type'] for e in self._events]
            raise AssertionError(f"Expected no events, but found: {types}")
