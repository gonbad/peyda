# معماری پروژه لِسان - بخش ۴: زیرساخت و تست

## ۱. Infrastructure Layer

### ۱.۱ ساختار

```
backend/infrastructure/
├── __init__.py
├── bootstrap.py              # DI Container
├── event_bus/
│   ├── __init__.py
│   ├── interface.py          # Abstract EventBus
│   ├── rabbitmq.py           # Production implementation
│   └── fake.py               # Testing implementation
├── cache/
│   ├── __init__.py
│   ├── interface.py          # Abstract Cache
│   ├── redis.py              # Production implementation
│   └── fake.py               # Testing implementation
└── clock/
    ├── __init__.py
    ├── interface.py          # Abstract Clock
    └── fake.py               # Testing implementation
```

### ۱.۲ Event Bus Interface

```python
# infrastructure/event_bus/interface.py
from abc import ABC, abstractmethod
from typing import Callable

class EventBus(ABC):
    """رابط Event Bus"""
    
    @abstractmethod
    def publish(self, event_type: str, payload: dict) -> None:
        """انتشار رویداد"""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """اشتراک در رویداد"""
        pass
        
    **HUMAN OVERRIDE**: we dont use subscribe. n8n listens on events and then calls some endpoints
```

### ۱.۳ RabbitMQ Implementation

```python
# infrastructure/event_bus/rabbitmq.py
import json
import pika
from .interface import EventBus

class RabbitMQEventBus(EventBus):
    def __init__(self, connection_url: str):
        self._connection = pika.BlockingConnection(
            pika.URLParameters(connection_url)
        )
        self._channel = self._connection.channel()
        self._exchange = 'peyda_events'
        self._channel.exchange_declare(
            exchange=self._exchange,
            exchange_type='topic'
        )
    
    def publish(self, event_type: str, payload: dict) -> None:
        self._channel.basic_publish(
            exchange=self._exchange,
            routing_key=event_type,
            body=json.dumps(payload)
        )
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        result = self._channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        
        self._channel.queue_bind(
            exchange=self._exchange,
            queue=queue_name,
            routing_key=event_type
        )
        
        def callback(ch, method, properties, body):
            payload = json.loads(body)
            handler(payload)
        
        self._channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True
        )
```

### ۱.۴ Fake Event Bus (برای تست)

```python
# infrastructure/event_bus/fake.py
from typing import Callable
from .interface import EventBus

class FakeEventBus(EventBus):
    """Event Bus برای تست - ذخیره رویدادها در حافظه"""
    
    def __init__(self):
        self._published: list[tuple[str, dict]] = []
        self._handlers: dict[str, list[Callable]] = {}
    
    def publish(self, event_type: str, payload: dict) -> None:
        self._published.append((event_type, payload))
        
        # فراخوانی handler های ثبت شده
        for handler in self._handlers.get(event_type, []):
            handler(payload)
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    # متدهای کمکی برای تست
    def get_published(self) -> list[tuple[str, dict]]:
        return self._published
    
    def clear(self) -> None:
        self._published.clear()
        self._handlers.clear()
```

### ۱.۵ Cache Interface

```python
# infrastructure/cache/interface.py
from abc import ABC, abstractmethod
from typing import Any, Optional

class Cache(ABC):
    """رابط Cache"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        pass
    
    @abstractmethod
    def clear(self) -> None:
        pass
```

### ۱.۶ Redis Implementation

```python
# infrastructure/cache/redis.py
import json
import redis
from typing import Any, Optional
from .interface import Cache

class RedisCache(Cache):
    def __init__(self, url: str):
        self._client = redis.from_url(url)
    
    def get(self, key: str) -> Optional[Any]:
        value = self._client.get(key)
        if value is None:
            return None
        return json.loads(value)
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._client.setex(key, ttl, json.dumps(value))
    
    def delete(self, key: str) -> None:
        self._client.delete(key)
    
    def clear(self) -> None:
        self._client.flushdb()
```

### ۱.۷ Fake Cache

```python
# infrastructure/cache/fake.py
from typing import Any, Optional
from .interface import Cache

class FakeCache(Cache):
    """Cache برای تست - ذخیره در حافظه"""
    
    def __init__(self):
        self._store: dict[str, Any] = {}
    
    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._store[key] = value
    
    def delete(self, key: str) -> None:
        self._store.pop(key, None)
    
    def clear(self) -> None:
        self._store.clear()
```

### ۱.۸ Clock Interface

```python
# infrastructure/clock/interface.py
from abc import ABC, abstractmethod
from datetime import datetime

class Clock(ABC):
    """رابط ساعت سیستم"""
    
    @abstractmethod
    def now(self) -> datetime:
        pass


class SystemClock(Clock):
    """ساعت واقعی سیستم"""
    
    def now(self) -> datetime:
        return datetime.now()
```

### ۱.۹ Fake Clock

```python
# infrastructure/clock/fake.py
from datetime import datetime, timedelta
from .interface import Clock

class FakeClock(Clock):
    """ساعت برای تست - زمان قابل کنترل"""
    
    def __init__(self, initial: datetime = None):
        self._current = initial or datetime(2024, 1, 1, 12, 0, 0)
    
    def now(self) -> datetime:
        return self._current
    
    def advance(self, **kwargs) -> None:
        """جلو بردن زمان"""
        self._current += timedelta(**kwargs)
    
    def set(self, time: datetime) -> None:
        """تنظیم زمان خاص"""
        self._current = time
```

### ۱.۱۰ Dependency Injection Container

```python
# infrastructure/bootstrap.py
from django.conf import settings
from .event_bus.interface import EventBus
from .event_bus.rabbitmq import RabbitMQEventBus
from .event_bus.fake import FakeEventBus
from .cache.interface import Cache
from .cache.redis import RedisCache
from .cache.fake import FakeCache
from .clock.interface import Clock, SystemClock
from .clock.fake import FakeClock

class Container:
    """DI Container"""
    
    def __init__(self):
        self._instances = {}
        self._factories = {}
    
    def register(self, interface, factory):
        self._factories[interface] = factory
    
    def get(self, interface):
        if interface not in self._instances:
            factory = self._factories.get(interface)
            if factory:
                self._instances[interface] = factory()
        return self._instances[interface]
    
    def reset(self):
        self._instances.clear()


_container = None

def get_container() -> Container:
    global _container
    if _container is None:
        _container = _create_container()
    return _container

def _create_container() -> Container:
    container = Container()
    
    if settings.TESTING:
        # Fake implementations for testing
        container.register(EventBus, FakeEventBus)
        container.register(Cache, FakeCache)
        container.register(Clock, FakeClock)
    else:
        # Production implementations
        container.register(EventBus, lambda: RabbitMQEventBus(
            settings.RABBITMQ_URL
        ))
        container.register(Cache, lambda: RedisCache(
            settings.REDIS_URL
        ))
        container.register(Clock, SystemClock)
    
    return container

def reset_container():
    """برای استفاده در تست‌ها"""
    global _container
    if _container:
        _container.reset()
    _container = None
```

---

## ۲. تست‌نویسی

### ۲.۱ اصول تست

| اصل | توضیح |
|-----|-------|
| **No Mocking** | از Fake استفاده می‌کنیم نه Mock |
| **Integration First** | تست‌های یکپارچگی اولویت بالاتر دارند |
| **Real Database** | استفاده از PostgreSQL واقعی (نه SQLite) |
| **Isolated** | هر تست مستقل از دیگری |

### ۲.۲ ساختار تست‌ها

```
backend/
├── apps/
│   ├── quran/
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       └── test_queries.py
│   ├── courses/
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       └── test_packaging.py
│   └── ...
├── services/
│   └── tests/
│       ├── __init__.py
│       ├── test_lesson_service.py
│       ├── test_progress_service.py
│       └── test_question_service.py
└── tests/
    ├── __init__.py
    ├── conftest.py              # pytest fixtures
    ├── integration/
    │   ├── __init__.py
    │   ├── test_api_courses.py
    │   ├── test_api_lessons.py
    │   └── test_api_progress.py
    └── e2e/
        ├── __init__.py
        └── test_lesson_flow.py
```

### ۲.۳ Pytest Fixtures

```python
# tests/conftest.py
import pytest
from django.test import override_settings
from infrastructure.bootstrap import reset_container, get_container
from infrastructure.event_bus.fake import FakeEventBus
from infrastructure.cache.fake import FakeCache
from infrastructure.clock.fake import FakeClock

@pytest.fixture(autouse=True)
def reset_infrastructure():
    """ریست کردن زیرساخت قبل از هر تست"""
    reset_container()
    yield
    reset_container()


@pytest.fixture
def event_bus():
    """دسترسی به FakeEventBus"""
    container = get_container()
    return container.get(FakeEventBus)


@pytest.fixture
def cache():
    """دسترسی به FakeCache"""
    container = get_container()
    return container.get(FakeCache)


@pytest.fixture
def clock():
    """دسترسی به FakeClock"""
    container = get_container()
    return container.get(FakeClock)


@pytest.fixture
def user(db):
    """ایجاد کاربر تست"""
    from apps.users.models import User
    return User.objects.create(
        platform='eitaa',
        platform_user_id='test_user_123',
        username='testuser'
    )


@pytest.fixture
def course_with_lessons(db):
    """ایجاد دوره با درس‌های تست"""
    from apps.courses.models import Course, Level, Juz, Stage, Lesson
    
    course = Course.objects.create(name='Test Course')
    level = Level.objects.create(
        course=course, number=1, order=10000, name='Level 1'
    )
    juz = Juz.objects.create(
        level=level, number=1,
        start_ayah_global_id=1, end_ayah_global_id=141
    )
    stage = Stage.objects.create(
        juz=juz, hizb_number=1, stage_type='normal', order=10000
    )
    lesson = Lesson.objects.create(
        stage=stage, order=10000, is_review=False
    )
    
    return {
        'course': course,
        'level': level,
        'juz': juz,
        'stage': stage,
        'lesson': lesson
    }
```

### ۲.۴ نمونه تست سرویس

```python
# services/tests/test_progress_service.py
import pytest
from datetime import datetime
from services.progress_service import ProgressService
from infrastructure.bootstrap import get_container

@pytest.mark.django_db
class TestProgressService:
    
    def test_submit_answer_correct(self, user, course_with_lessons, event_bus, clock):
        """تست ثبت پاسخ صحیح"""
        # Arrange
        container = get_container()
        service = ProgressService(
            event_bus=container.get(EventBus),
            cache=container.get(Cache),
            clock=container.get(Clock)
        )
        lesson = course_with_lessons['lesson']
        
        # Act
        result = service.submit_answer(
            user_id=user.id,
            question_id=1,
            lesson_id=lesson.id,
            answer={'selected': 'a'},
            is_correct=True,
            time_spent_ms=5000
        )
        
        # Assert
        assert result['is_correct'] is True
        assert 'answer_id' in result
        
        # Check event was published
        events = event_bus.get_published()
        assert len(events) == 1
        assert events[0][0] == 'answer.submitted'
        assert events[0][1]['is_correct'] is True
    
    def test_complete_lesson_calculates_score(self, user, course_with_lessons):
        """تست محاسبه امتیاز پایان درس"""
        # Arrange
        container = get_container()
        service = ProgressService(
            event_bus=container.get(EventBus),
            cache=container.get(Cache),
            clock=container.get(Clock)
        )
        lesson = course_with_lessons['lesson']
        
        # Submit some answers
        for i in range(7):
            service.submit_answer(
                user_id=user.id,
                question_id=i,
                lesson_id=lesson.id,
                answer={},
                is_correct=(i < 5),  # 5 correct, 2 wrong
                time_spent_ms=1000
            )
        
        # Act
        result = service.complete_lesson(user.id, lesson.id)
        
        # Assert
        assert result['status'] == 'completed'
        assert result['correct_count'] == 5
        assert result['wrong_count'] == 2
        assert result['score'] == 71  # 5/7 * 100
```

### ۲.۵ نمونه تست API

```python
# tests/integration/test_api_progress.py
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestProgressAPI:
    
    def test_submit_answer_endpoint(self, user, course_with_lessons):
        """تست endpoint ثبت پاسخ"""
        client = APIClient()
        client.force_authenticate(user=user)
        
        lesson = course_with_lessons['lesson']
        
        response = client.post('/api/v1/answers/', {
            'question_id': 1,
            'lesson_id': lesson.id,
            'answer': {'selected': 'a'},
            'is_correct': True,
            'time_spent_ms': 3000
        })
        
        assert response.status_code == 200
        assert response.data['is_correct'] is True
    
    def test_get_user_progress(self, user):
        """تست دریافت پیشرفت کاربر"""
        client = APIClient()
        client.force_authenticate(user=user)
        
        response = client.get('/api/v1/me/progress/')
        
        assert response.status_code == 200
        assert 'current_juz_id' in response.data
```

### ۲.۶ تست E2E (جریان کامل)

```python
# tests/e2e/test_lesson_flow.py
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestLessonFlow:
    """تست جریان کامل یک درس"""
    
    def test_complete_lesson_flow(self, user, course_with_lessons, questions):
        """کاربر یک درس را کامل می‌کند"""
        client = APIClient()
        client.force_authenticate(user=user)
        
        lesson = course_with_lessons['lesson']
        
        # 1. Get lesson questions
        response = client.get(f'/api/v1/lessons/{lesson.id}/questions/')
        assert response.status_code == 200
        questions = response.data
        
        # 2. Answer all questions
        for q in questions:
            response = client.post('/api/v1/answers/', {
                'question_id': q['id'],
                'lesson_id': lesson.id,
                'answer': {'selected': 'a'},
                'is_correct': True,
                'time_spent_ms': 2000
            })
            assert response.status_code == 200
        
        # 3. Complete lesson
        response = client.post(f'/api/v1/lessons/{lesson.id}/complete/')
        assert response.status_code == 200
        assert response.data['status'] == 'completed'
        
        # 4. Check progress updated
        response = client.get('/api/v1/me/progress/')
        assert response.status_code == 200
```

---

## ۳. Docker Compose

### ۳.۱ Development

```yaml
# config/develop/docker-compose.yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: peyda
      POSTGRES_USER: peyda
      POSTGRES_PASSWORD: peyda
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U peyda"]
      interval: 5s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: peyda
      RABBITMQ_DEFAULT_PASS: peyda
    ports:
      - "5672:5672"
      - "15672:15672"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    build:
      context: ../../backend
      dockerfile: Dockerfile
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ../../backend:/app
      - ../../resources:/resources
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgres://peyda:peyda@db:5432/peyda
      RABBITMQ_URL: amqp://peyda:peyda@rabbitmq:5672/
      REDIS_URL: redis://redis:6379/0
      DEBUG: "true"
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_started

volumes:
  postgres_data:
```

### ۳.۲ Production (Simplified)

```yaml
# config/production/docker-compose.yaml
services:
  api:
    image: peyda-api:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
      RABBITMQ_URL: ${RABBITMQ_URL}
      REDIS_URL: ${REDIS_URL}
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: "false"
    deploy:
      replicas: 2
```

---

## ۴. Management Commands

### ۴.۱ لیست دستورات

| دستور | توضیح |
|-------|-------|
| `import_quran_excel` | وارد کردن قرآن از Excel |
| `import_morphology` | وارد کردن تحلیل مورفولوژی |
| `import_word_translations` | وارد کردن ترجمه کلمات |
| `import_famous_verses` | وارد کردن آیات معروف |
| `import_csv_questions` | وارد کردن سوالات از CSV |
| `generate_syllabi` | تولید درسنامه اجزاء |
| `package_questions` | بسته‌بندی سوالات در درس‌ها |

### ۴.۲ اجرا

```bash
# Development
docker compose exec api python manage.py import_quran_excel
docker compose exec api python manage.py generate_syllabi --clear
docker compose exec api python manage.py package_questions --clear
```

---

## ۵. Portability (قابلیت انتقال)

### ۵.۱ داده‌ها
- فایل‌های منبع در `resources/`
- Management commands برای import/export
- Fixtures برای داده‌های اولیه

### ۵.۲ Workflows
- تعریف به صورت کد (قابل version control)
- اعتبارسنجی در n8n GUI
- انتقال به production با export/import
