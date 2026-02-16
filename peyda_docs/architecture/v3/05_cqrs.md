# معماری لِسان v3 - CQRS (Command Query Responsibility Segregation)

## ۱. اصول CQRS

### ۱.۱ تفکیک Command و Query

| نوع | وظیفه | Side Effect | Return |
|-----|-------|-------------|--------|
| **Command** | تغییر state | ✅ دارد | نتیجه عملیات |
| **Query** | خواندن داده | ❌ ندارد | داده |

### ۱.۲ ساختار فایل‌ها

```
backend/
└── services/
    ├── commands/                     # Write operations
    │   ├── base.py
    │   ├── complete_lesson.py
    │   ├── submit_feedback.py
    │   ├── grant_achievement.py
    │   ├── save_notification_result.py
    │   ├── invalidate_cache.py
    │   └── log_admin_action.py
    │
    ├── queries/                      # Read operations
    │   ├── base.py
    │   ├── get_lesson_questions.py
    │   ├── get_user_progress.py
    │   ├── get_juz_detail.py
    │   └── get_syllabus.py
    │
    └── __init__.py
```

---

## ۲. Base Classes

### ۲.۱ Base Command

```python
# services/commands/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
import logging
from infrastructure.event_bus import EventBus
from infrastructure.clock import Clock

T = TypeVar('T')

class BaseCommand(ABC, Generic[T]):
    """پایه همه Command ها"""
    
    def __init__(
        self,
        event_bus: EventBus,
        clock: Clock,
        logger: logging.Logger = None
    ):
        self._event_bus = event_bus
        self._clock = clock
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, **kwargs) -> T:
        """اجرای command - باید در subclass پیاده‌سازی شود"""
        pass
    
    def publish_event(self, event_type: str, payload: dict):
        """انتشار رویداد"""
        # Always add timestamp as Unix timestamp
        payload['timestamp'] = int(self._clock.now().timestamp())
        self._event_bus.publish(event_type, payload)
    
    def log_info(self, message: str, **extra):
        """Log با context"""
        self._logger.info(message, extra=extra)
    
    def log_error(self, message: str, **extra):
        """Log خطا"""
        self._logger.error(message, extra=extra)
```

### ۲.۲ Base Query

```python
# services/queries/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional
import logging
from infrastructure.cache import Cache
from infrastructure.clock import Clock

T = TypeVar('T')

class BaseQuery(ABC, Generic[T]):
    """پایه همه Query ها"""
    
    def __init__(
        self,
        cache: Optional[Cache] = None,
        clock: Optional[Clock] = None,
        logger: logging.Logger = None
    ):
        self._cache = cache
        self._clock = clock
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, **kwargs) -> T:
        """اجرای query - باید در subclass پیاده‌سازی شود"""
        pass
    
    def get_cached(self, key: str) -> Optional[T]:
        """دریافت از کش"""
        if self._cache:
            return self._cache.get(key)
        return None
    
    def set_cached(self, key: str, value: T, ttl: int = 3600):
        """ذخیره در کش"""
        if self._cache:
            self._cache.set(key, value, ttl=ttl)
```

---

## ۳. Commands

### ۳.۱ Complete Lesson Command

```python
# services/commands/complete_lesson.py
from typing import List
from datetime import datetime
from django.db import transaction
from apps.progress.models import LessonProgress, FailedQuestion, UserProgress
from apps.courses.models import Lesson, LessonQuestion
from .base import BaseCommand

class CompleteLessonResult:
    def __init__(
        self,
        lesson_id: int,
        correct_count: int,
        wrong_count: int,
        score: int,
        xp_earned: int,
        completed_at: int
    ):
        self.lesson_id = lesson_id
        self.correct_count = correct_count
        self.wrong_count = wrong_count
        self.score = score
        self.xp_earned = xp_earned
        self.completed_at = completed_at


class CompleteLessonCommand(BaseCommand[CompleteLessonResult]):
    """تکمیل درس"""
    
    @transaction.atomic
    def execute(
        self,
        user_id: int,
        lesson_id: int,
        failed_question_ids: List[int],
        total_time_ms: int,
        client_timestamp: int
    ) -> CompleteLessonResult:
        
        # 1. Get lesson with related data
        lesson = Lesson.objects.select_related('stage__juz').get(id=lesson_id)
        total_questions = LessonQuestion.objects.filter(lesson_id=lesson_id).count()
        
        # 2. Calculate
        wrong_count = len(failed_question_ids)
        correct_count = total_questions - wrong_count
        
        # 3. Validate
        if wrong_count > total_questions:
            raise ValueError("تعداد پاسخ‌های اشتباه بیشتر از تعداد سوالات")
        
        # 4. Check for existing (idempotent)
        existing = LessonProgress.objects.select_for_update().filter(
            user_id=user_id,
            lesson_id=lesson_id,
            status='completed'
        ).first()
        
        if existing:
            return self._build_result(existing, lesson)
        
        # 5. Create progress
        now = self._clock.now()
        progress, _ = LessonProgress.objects.update_or_create(
            user_id=user_id,
            lesson_id=lesson_id,
            defaults={
                'status': 'completed',
                'correct_count': correct_count,
                'wrong_count': wrong_count,
                'total_time_ms': total_time_ms,
                'completed_at': now
            }
        )
        
        # 6. Record failed questions
        if failed_question_ids:
            FailedQuestion.objects.bulk_create([
                FailedQuestion(
                    user_id=user_id,
                    question_id=qid,
                    lesson_id=lesson_id
                )
                for qid in failed_question_ids
            ], ignore_conflicts=True)
        
        # 7. Update user progress pointer
        UserProgress.objects.update_or_create(
            user_id=user_id,
            defaults={
                'current_juz_id': lesson.stage.juz.id,
                'current_stage_id': lesson.stage.id,
                'current_lesson_id': lesson.id
            }
        )
        
        # 8. Calculate score & XP
        score = self._calculate_score(correct_count, total_questions)
        xp = self._calculate_xp(score, lesson.stage.juz.number)
        
        # 9. Publish event
        self.publish_event('lesson.completed', {
            'user_id': user_id,
            'lesson_id': lesson_id,
            'juz_id': lesson.stage.juz.id,
            'stage_id': lesson.stage.id,
            'score': score,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'failed_question_ids': failed_question_ids,
            'total_time_ms': total_time_ms
        })
        
        self.log_info(
            "Lesson completed",
            user_id=user_id,
            lesson_id=lesson_id,
            score=score
        )
        
        return CompleteLessonResult(
            lesson_id=lesson_id,
            correct_count=correct_count,
            wrong_count=wrong_count,
            score=score,
            xp_earned=xp,
            completed_at=int(now.timestamp())
        )
    
    def _calculate_score(self, correct: int, total: int) -> int:
        if total == 0:
            return 0
        return int((correct / total) * 100)
    
    def _calculate_xp(self, score: int, juz_number: int) -> int:
        base_xp = 10
        score_multiplier = score / 100
        juz_bonus = juz_number
        return int(base_xp * score_multiplier * (1 + juz_bonus * 0.1))
    
    def _build_result(self, progress: LessonProgress, lesson: Lesson) -> CompleteLessonResult:
        score = self._calculate_score(progress.correct_count, 
                                       progress.correct_count + progress.wrong_count)
        xp = self._calculate_xp(score, lesson.stage.juz.number)
        return CompleteLessonResult(
            lesson_id=progress.lesson_id,
            correct_count=progress.correct_count,
            wrong_count=progress.wrong_count,
            score=score,
            xp_earned=xp,
            completed_at=int(progress.completed_at.timestamp())
        )
```

### ۳.۲ Grant Achievement Command

```python
# services/commands/grant_achievement.py
from django.db import transaction
from django.db.models import F
from apps.progress.models import UserAchievement, UserProgress
from .base import BaseCommand

class GrantAchievementCommand(BaseCommand[bool]):
    """ثبت دستاورد کاربر"""
    
    @transaction.atomic
    def execute(
        self,
        user_id: int,
        achievement_type: str,
        xp_amount: int = 0
    ) -> bool:
        
        # Check if already has this achievement
        existing = UserAchievement.objects.filter(
            user_id=user_id,
            achievement_type=achievement_type
        ).exists()
        
        if existing:
            self.log_info(
                "Achievement already granted",
                user_id=user_id,
                achievement_type=achievement_type
            )
            return False
        
        # Create achievement
        UserAchievement.objects.create(
            user_id=user_id,
            achievement_type=achievement_type
        )
        
        # Update XP
        if xp_amount > 0:
            UserProgress.objects.filter(user_id=user_id).update(
                total_xp=F('total_xp') + xp_amount
            )
        
        # Publish event
        self.publish_event('achievement.granted', {
            'user_id': user_id,
            'achievement_type': achievement_type,
            'xp_amount': xp_amount
        })
        
        self.log_info(
            "Achievement granted",
            user_id=user_id,
            achievement_type=achievement_type,
            xp_amount=xp_amount
        )
        
        return True
```

### ۳.۳ Invalidate Cache Command

```python
# services/commands/invalidate_cache.py
from infrastructure.cache import Cache
from .base import BaseCommand

class InvalidateCacheCommand(BaseCommand[bool]):
    """Invalidate کردن کش"""
    
    def __init__(self, cache: Cache, **kwargs):
        super().__init__(**kwargs)
        self._cache_service = cache
    
    def execute(self, cache_key: str) -> bool:
        self._cache_service.delete(cache_key)
        
        self.log_info(
            "Cache invalidated",
            cache_key=cache_key
        )
        
        return True
```

---

## ۴. Queries

### ۴.۱ Get Lesson Questions Query

```python
# services/queries/get_lesson_questions.py
from typing import List, Dict, Any
from django.db.models import Case, When
from apps.questions.models import Question
from apps.courses.models import LessonQuestion
from .base import BaseQuery

class GetLessonQuestionsQuery(BaseQuery[List[Dict[str, Any]]]):
    """دریافت سوالات یک درس"""
    
    def execute(self, lesson_id: int) -> List[Dict[str, Any]]:
        # Check cache
        cache_key = f"lesson:{lesson_id}:questions"
        cached = self.get_cached(cache_key)
        if cached:
            return cached
        
        # Get ordered question IDs
        question_ids = list(
            LessonQuestion.objects
            .filter(lesson_id=lesson_id)
            .order_by('order')
            .values_list('question_id', flat=True)
        )
        
        if not question_ids:
            return []
        
        # Preserve order using Case/When
        preserved_order = Case(*[
            When(pk=pk, then=pos) 
            for pos, pk in enumerate(question_ids)
        ])
        
        # Fetch questions
        questions = Question.objects.filter(
            id__in=question_ids,
            is_active=True
        ).order_by(preserved_order)
        
        # Serialize
        result = [self._serialize(q) for q in questions]
        
        # Cache for 1 hour
        self.set_cached(cache_key, result, ttl=3600)
        
        return result
    
    def _serialize(self, question: Question) -> Dict[str, Any]:
        return {
            'id': question.id,
            'type': question.question_type,
            'content': question.content,
            'difficulty': question.difficulty
        }
```

### ۴.۲ Get User Progress Query

```python
# services/queries/get_user_progress.py
from typing import Optional, Dict, Any
from apps.progress.models import UserProgress, LessonProgress
from .base import BaseQuery

class GetUserProgressQuery(BaseQuery[Dict[str, Any]]):
    """دریافت پیشرفت کاربر"""
    
    def execute(self, user_id: int) -> Dict[str, Any]:
        # Get user progress
        progress = UserProgress.objects.filter(user_id=user_id).first()
        
        if not progress:
            return {
                'current_juz_id': None,
                'current_stage_id': None,
                'current_lesson_id': None,
                'total_completed_lessons': 0,
                'total_xp': 0,
                'last_activity_at': None
            }
        
        # Count completed lessons
        completed_count = LessonProgress.objects.filter(
            user_id=user_id,
            status='completed'
        ).count()
        
        # Get last activity
        last_lesson = LessonProgress.objects.filter(
            user_id=user_id,
            status='completed'
        ).order_by('-completed_at').first()
        
        last_activity_at = None
        if last_lesson and last_lesson.completed_at:
            last_activity_at = int(last_lesson.completed_at.timestamp())
        
        return {
            'current_juz_id': progress.current_juz_id,
            'current_stage_id': progress.current_stage_id,
            'current_lesson_id': progress.current_lesson_id,
            'total_completed_lessons': completed_count,
            'total_xp': progress.total_xp,
            'last_activity_at': last_activity_at
        }
```

### ۴.۳ Get Juz Detail Query

```python
# services/queries/get_juz_detail.py
from typing import Dict, Any, List
from apps.courses.models import Juz, Stage
from .base import BaseQuery

class GetJuzDetailQuery(BaseQuery[Dict[str, Any]]):
    """دریافت جزئیات جزء"""
    
    def execute(self, juz_id: int) -> Dict[str, Any]:
        # Check cache
        cache_key = f"juz:{juz_id}:detail"
        cached = self.get_cached(cache_key)
        if cached:
            return cached
        
        # Get juz
        juz = Juz.objects.get(id=juz_id)
        
        # Get stages
        stages = Stage.objects.filter(juz_id=juz_id).order_by('order')
        
        result = {
            'id': juz.id,
            'number': juz.number,
            'stages': [
                {
                    'id': s.id,
                    'hizb_number': s.hizb_number,
                    'stage_type': s.stage_type,
                    'order': s.order
                }
                for s in stages
            ]
        }
        
        # Cache for 1 hour
        self.set_cached(cache_key, result, ttl=3600)
        
        return result
```

### ۴.۴ Get Syllabus Query

```python
# services/queries/get_syllabus.py
from typing import Optional, Dict, Any
from apps.courses.models import Syllabus
from .base import BaseQuery

class GetSyllabusQuery(BaseQuery[Optional[Dict[str, Any]]]):
    """دریافت درسنامه جزء"""
    
    def execute(self, juz_id: int) -> Optional[Dict[str, Any]]:
        # Check cache
        cache_key = f"juz:{juz_id}:syllabus"
        cached = self.get_cached(cache_key)
        if cached:
            return cached
        
        # Get syllabus
        syllabus = Syllabus.objects.filter(juz_id=juz_id).first()
        
        if not syllabus:
            return None
        
        result = {
            'juz_id': juz_id,
            'content': syllabus.content
        }
        
        # Cache for 6 hours (syllabus rarely changes)
        self.set_cached(cache_key, result, ttl=21600)
        
        return result
```

---

## ۵. Dependency Injection

### ۵.۱ Container Configuration

```python
# infrastructure/bootstrap.py
from infrastructure.event_bus import RabbitMQEventBus
from infrastructure.cache import RedisCache
from infrastructure.clock import SystemClock
from services.commands.complete_lesson import CompleteLessonCommand
from services.commands.grant_achievement import GrantAchievementCommand
from services.commands.save_notification_result import SaveNotificationResultCommand
from services.commands.invalidate_cache import InvalidateCacheCommand
from services.queries.get_lesson_questions import GetLessonQuestionsQuery
from services.queries.get_user_progress import GetUserProgressQuery
from services.queries.get_juz_detail import GetJuzDetailQuery
from services.queries.get_syllabus import GetSyllabusQuery

class Container:
    _instance = None
    
    def __init__(self):
        # Infrastructure
        self._event_bus = RabbitMQEventBus(settings.RABBITMQ_URL)
        self._cache = RedisCache(settings.REDIS_URL)
        self._clock = SystemClock()
        
        # Commands
        self._commands = {}
        self._queries = {}
    
    def get(self, cls):
        """Get instance of command or query"""
        
        # Commands
        if cls == CompleteLessonCommand:
            return CompleteLessonCommand(
                event_bus=self._event_bus,
                clock=self._clock
            )
        
        if cls == GrantAchievementCommand:
            return GrantAchievementCommand(
                event_bus=self._event_bus,
                clock=self._clock
            )
        
        if cls == SaveNotificationResultCommand:
            return SaveNotificationResultCommand(
                event_bus=self._event_bus,
                clock=self._clock
            )
        
        if cls == InvalidateCacheCommand:
            return InvalidateCacheCommand(
                cache=self._cache,
                event_bus=self._event_bus,
                clock=self._clock
            )
        
        # Queries
        if cls == GetLessonQuestionsQuery:
            return GetLessonQuestionsQuery(
                cache=self._cache,
                clock=self._clock
            )
        
        if cls == GetUserProgressQuery:
            return GetUserProgressQuery(
                cache=self._cache,
                clock=self._clock
            )
        
        if cls == GetJuzDetailQuery:
            return GetJuzDetailQuery(
                cache=self._cache,
                clock=self._clock
            )
        
        if cls == GetSyllabusQuery:
            return GetSyllabusQuery(
                cache=self._cache,
                clock=self._clock
            )
        
        raise ValueError(f"Unknown type: {cls}")
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_container() -> Container:
    return Container.instance()
```

---

## ۶. Usage in Interface Layer

```python
# apps/api/viewsets/progress.py
class LessonViewSet(BaseViewSet):
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """GET /api/v1/lessons/{id}/questions/"""
        
        # Use Query
        query = self.get_query(GetLessonQuestionsQuery)
        questions = query.execute(lesson_id=int(pk))
        
        return Response({
            'lesson_id': int(pk),
            'questions': questions,
            'total_count': len(questions)
        })
    
    @action(detail=True, methods=['post'])
    @idempotent
    def complete(self, request, pk=None):
        """POST /api/v1/lessons/{id}/complete/"""
        
        # Validate
        req, error = self.validate_request(CompleteLessonRequest, request.data)
        if error:
            return error
        
        # Use Command
        command = self.get_command(CompleteLessonCommand)
        result = command.execute(
            user_id=request.user.id,
            lesson_id=int(pk),
            failed_question_ids=req.failed_question_ids,
            total_time_ms=req.total_time_ms,
            client_timestamp=req.client_timestamp
        )
        
        return self.success(result, CompleteLessonResponse)
```

---

## ۷. Testing

### ۷.۱ Testing Commands

```python
# tests/services/commands/test_complete_lesson.py
import pytest
from services.commands.complete_lesson import CompleteLessonCommand
from infrastructure.event_bus import FakeEventBus
from infrastructure.clock import FakeClock

class TestCompleteLessonCommand:
    
    @pytest.fixture
    def command(self):
        return CompleteLessonCommand(
            event_bus=FakeEventBus(),
            clock=FakeClock()
        )
    
    def test_complete_lesson_success(self, command, lesson_factory):
        lesson = lesson_factory()
        
        result = command.execute(
            user_id=1,
            lesson_id=lesson.id,
            failed_question_ids=[],
            total_time_ms=60000,
            client_timestamp=1705329000
        )
        
        assert result.score == 100
        assert result.wrong_count == 0
    
    def test_complete_lesson_with_failures(self, command, lesson_factory):
        lesson = lesson_factory(question_count=10)
        
        result = command.execute(
            user_id=1,
            lesson_id=lesson.id,
            failed_question_ids=[1, 2, 3],
            total_time_ms=60000,
            client_timestamp=1705329000
        )
        
        assert result.correct_count == 7
        assert result.wrong_count == 3
        assert result.score == 70
```

### ۷.۲ Testing Queries

```python
# tests/services/queries/test_get_lesson_questions.py
import pytest
from services.queries.get_lesson_questions import GetLessonQuestionsQuery
from infrastructure.cache import FakeCache

class TestGetLessonQuestionsQuery:
    
    @pytest.fixture
    def query(self):
        return GetLessonQuestionsQuery(
            cache=FakeCache()
        )
    
    def test_returns_ordered_questions(self, query, lesson_with_questions):
        lesson = lesson_with_questions(count=5)
        
        result = query.execute(lesson_id=lesson.id)
        
        assert len(result) == 5
        assert all('id' in q for q in result)
        assert all('type' in q for q in result)
    
    def test_caches_result(self, query, lesson_with_questions):
        lesson = lesson_with_questions(count=3)
        
        # First call
        result1 = query.execute(lesson_id=lesson.id)
        
        # Second call should hit cache
        result2 = query.execute(lesson_id=lesson.id)
        
        assert result1 == result2
```

---

## ۸. مزایای CQRS

| مزیت | توضیح |
|------|-------|
| **Separation of Concerns** | کد خوانا‌تر و قابل نگهداری‌تر |
| **Scalability** | امکان scale جداگانه read و write |
| **Testability** | تست آسان‌تر با mock کمتر |
| **Caching** | کش کردن آسان query ها |
| **Audit Trail** | ردیابی آسان تغییرات |
