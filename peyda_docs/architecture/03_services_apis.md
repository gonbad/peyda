# معماری پروژه لِسان - بخش ۳: سرویس‌ها و API

## ۱. Application Layer (سرویس‌ها)

### ۱.۱ ساختار سرویس‌ها

```python
backend/services/
├── __init__.py
├── base.py                 # BaseService with DI
├── quran_service.py
├── lesson_service.py
├── question_service.py
├── progress_service.py
└── auth_service.py
```

### ۱.۲ BaseService (پایه)

```python
# services/base.py
from infrastructure import EventBus, Cache, Clock

class BaseService:
    """پایه همه سرویس‌ها با Dependency Injection"""
    
    def __init__(
        self,
        event_bus: EventBus,
        cache: Cache,
        clock: Clock
    ):
        self._event_bus = event_bus
        self._cache = cache
        self._clock = clock
```

### ۱.۳ QuranService

```python
# services/quran_service.py
from apps.quran.models import Surah, Ayah, Word

class QuranService(BaseService):
    
    def get_surah_list(self) -> list[dict]:
        """لیست سوره‌ها"""
        return list(Surah.objects.values(
            'number', 'name_arabic', 'name_persian', 'ayah_count'
        ))
    
    def get_ayahs_by_juz(self, juz_number: int) -> list[dict]:
        """آیات یک جزء"""
        cache_key = f"juz:{juz_number}:ayahs"
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        ayahs = Ayah.objects.filter(
            juz_number=juz_number
        ).select_related('surah').values(
            'global_number', 'number', 'text_arabic',
            'translation_maleki', 'surah__name_arabic'
        )
        
        result = list(ayahs)
        self._cache.set(cache_key, result, ttl=3600)
        return result
    
    def get_words_by_ayah(self, ayah_global_id: int) -> list[dict]:
        """کلمات یک آیه"""
        return list(Word.objects.filter(
            ayah__global_number=ayah_global_id
        ).order_by('position').values(
            'position', 'text_arabic', 'translation_persian', 'root'
        ))
    
    def get_juz_words(self, juz_number: int) -> list[dict]:
        """همه کلمات یک جزء (برای cache فرانت)"""
        cache_key = f"juz:{juz_number}:words"
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        words = Word.objects.filter(
            ayah__juz_number=juz_number
        ).select_related('ayah').values(
            'ayah__global_number', 'position',
            'text_arabic', 'translation_persian'
        )
        
        result = list(words)
        self._cache.set(cache_key, result, ttl=3600)
        return result
```

### ۱.۴ LessonService

```python
# services/lesson_service.py
from apps.courses.models import Course, Level, Juz, Stage, Lesson, Syllabus

class LessonService(BaseService):
    
    def get_courses(self) -> list[dict]:
        """لیست دوره‌های فعال"""
        return list(Course.objects.filter(
            is_active=True
        ).values('id', 'name', 'description'))
    
    def get_levels(self, course_id: int) -> list[dict]:
        """سطوح یک دوره"""
        return list(Level.objects.filter(
            course_id=course_id
        ).order_by('order').values(
            'id', 'number', 'name', 'focus', 'is_active'
        ))
    
    def get_juz_list(self, level_id: int) -> list[dict]:
        """اجزاء یک سطح"""
        return list(Juz.objects.filter(
            level_id=level_id
        ).order_by('number').values(
            'id', 'number', 'start_ayah_global_id', 'end_ayah_global_id'
        ))
    
    def get_juz_detail(self, juz_id: int) -> dict:
        """جزئیات جزء شامل مراحل"""
        juz = Juz.objects.get(id=juz_id)
        stages = Stage.objects.filter(
            juz=juz, is_visible=True
        ).order_by('order').values(
            'id', 'hizb_number', 'stage_type', 'order'
        )
        
        return {
            'id': juz.id,
            'number': juz.number,
            'stages': list(stages)
        }
    
    def get_syllabus(self, juz_id: int) -> dict:
        """درسنامه جزء"""
        cache_key = f"juz:{juz_id}:syllabus"
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        syllabus = Syllabus.objects.filter(
            juz_id=juz_id
        ).first()
        
        if not syllabus:
            return None
        
        result = {
            'id': syllabus.id,
            'type': syllabus.syllabus_type,
            'content': syllabus.content
        }
        
        self._cache.set(cache_key, result, ttl=3600)
        return result
    
    def get_stage_lessons(self, stage_id: int) -> list[dict]:
        """درس‌های یک مرحله"""
        return list(Lesson.objects.filter(
            stage_id=stage_id
        ).order_by('order').values(
            'id', 'order', 'is_review'
        ))
```

### ۱.۵ QuestionService

```python
# services/question_service.py
from apps.questions.models import Question
from apps.courses.models import LessonQuestion

class QuestionService(BaseService):
    
    def get_lesson_questions(self, lesson_id: int) -> list[dict]:
        """سوالات یک درس به ترتیب"""
        question_ids = LessonQuestion.objects.filter(
            lesson_id=lesson_id
        ).order_by('order').values_list('question_id', flat=True)
        
        questions = Question.objects.filter(
            id__in=question_ids,
            is_active=True
        )
        
        # حفظ ترتیب
        questions_map = {q.id: q for q in questions}
        ordered = [questions_map[qid] for qid in question_ids if qid in questions_map]
        
        return [
            {
                'id': q.id,
                'type': q.question_type,
                'content': q.content,
                'difficulty': q.difficulty
            }
            for q in ordered
        ]
    
    def submit_feedback(
        self,
        question_id: int,
        user_id: int,
        is_positive: bool
    ) -> None:
        """ثبت بازخورد سوال"""
        from apps.questions.models import QuestionFeedback
        
        QuestionFeedback.objects.update_or_create(
            question_id=question_id,
            user_id=user_id,
            defaults={'is_positive': is_positive}
        )
        
        # Update question score
        score_delta = 1 if is_positive else -1
        Question.objects.filter(id=question_id).update(
            feedback_score=models.F('feedback_score') + score_delta
        )
        
        # Publish event
        self._event_bus.publish('question.feedback', {
            'question_id': question_id,
            'user_id': user_id,
            'is_positive': is_positive,
            'timestamp': self._clock.now().isoformat()
        })
```

### ۱.۶ ProgressService

```python
# services/progress_service.py
from apps.progress.models import UserProgress, LessonProgress, UserAnswer

class ProgressService(BaseService):
    
    def get_user_progress(self, user_id: int) -> dict:
        """پیشرفت کلی کاربر"""
        progress, _ = UserProgress.objects.get_or_create(user_id=user_id)
        
        return {
            'current_juz_id': progress.current_juz_id,
            'current_stage_id': progress.current_stage_id,
            'current_lesson_id': progress.current_lesson_id
        }
    
    def get_lesson_progress(self, user_id: int, lesson_id: int) -> dict:
        """پیشرفت درس"""
        progress, _ = LessonProgress.objects.get_or_create(
            user_id=user_id,
            lesson_id=lesson_id,
            defaults={'status': 'not_started'}
        )
        
        return {
            'status': progress.status,
            'correct_count': progress.correct_count,
            'wrong_count': progress.wrong_count
        }
    
    def submit_answer(
        self,
        user_id: int,
        question_id: int,
        lesson_id: int,
        answer: dict,
        is_correct: bool,
        time_spent_ms: int
    ) -> dict:
        """ثبت پاسخ کاربر"""
        
        # Save answer
        user_answer = UserAnswer.objects.create(
            user_id=user_id,
            question_id=question_id,
            lesson_id=lesson_id,
            answer=answer,
            is_correct=is_correct,
            time_spent_ms=time_spent_ms
        )
        
        # Update lesson progress
        lesson_progress, _ = LessonProgress.objects.get_or_create(
            user_id=user_id,
            lesson_id=lesson_id,
            defaults={'status': 'in_progress'}
        )
        
        if is_correct:
            lesson_progress.correct_count += 1
        else:
            lesson_progress.wrong_count += 1
        
        lesson_progress.status = 'in_progress'
        lesson_progress.save()
        
        # Publish event
        self._event_bus.publish('answer.submitted', {
            'user_id': user_id,
            'question_id': question_id,
            'lesson_id': lesson_id,
            'is_correct': is_correct,
            'timestamp': self._clock.now().isoformat()
        })
        
        return {
            'answer_id': user_answer.id,
            'is_correct': is_correct
        }
    
    def complete_lesson(self, user_id: int, lesson_id: int) -> dict:
        """تکمیل درس"""
        progress = LessonProgress.objects.get(
            user_id=user_id,
            lesson_id=lesson_id
        )
        progress.status = 'completed'
        progress.save()
        
        # Publish event
        self._event_bus.publish('lesson.completed', {
            'user_id': user_id,
            'lesson_id': lesson_id,
            'correct_count': progress.correct_count,
            'wrong_count': progress.wrong_count,
            'timestamp': self._clock.now().isoformat()
        })
        
        return {
            'status': 'completed',
            'correct_count': progress.correct_count,
            'wrong_count': progress.wrong_count,
            'score': self._calculate_score(progress)
        }
    
    def _calculate_score(self, progress: LessonProgress) -> int:
        """محاسبه امتیاز"""
        total = progress.correct_count + progress.wrong_count
        if total == 0:
            return 0
        return int((progress.correct_count / total) * 100)
```

### ۱.۷ AuthService

```python
# services/auth_service.py
from apps.users.models import User

class AuthService(BaseService):
    
    def authenticate_messenger_token(self, token: str) -> User:
        """احراز هویت از توکن پیام‌رسان"""
        payload = self._verify_token(token)
        
        user, created = User.objects.get_or_create(
            platform=payload['platform'],
            platform_user_id=payload['platform_user_id'],
            defaults={
                'username': payload.get('username'),
                'display_name': payload.get('display_name')
            }
        )
        
        if created:
            self._event_bus.publish('user.created', {
                'user_id': user.id,
                'platform': user.platform,
                'timestamp': self._clock.now().isoformat()
            })
        
        return user
    
    def _verify_token(self, token: str) -> dict:
        """اعتبارسنجی توکن - بسته به پلتفرم"""
        # Implementation depends on messenger platform
        pass
```

---

## ۲. REST API Endpoints

### ۲.۱ URL Structure

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
]

# apps/api/urls.py
urlpatterns = [
    # Courses
    path('courses/', CourseListView.as_view()),
    path('courses/<int:pk>/levels/', LevelListView.as_view()),
    path('levels/<int:pk>/juz/', JuzListView.as_view()),
    path('juz/<int:pk>/', JuzDetailView.as_view()),
    path('juz/<int:pk>/syllabus/', SyllabusView.as_view()),
    path('stages/<int:pk>/lessons/', LessonListView.as_view()),
    path('lessons/<int:pk>/questions/', QuestionListView.as_view()),
    
    # Quran
    path('juz/<int:juz_number>/words/', JuzWordsView.as_view()),
    path('ayah/<int:global_id>/', AyahDetailView.as_view()),
    
    # Progress
    path('me/progress/', UserProgressView.as_view()),
    path('me/lessons/<int:lesson_id>/progress/', LessonProgressView.as_view()),
    
    # Answers
    path('answers/', SubmitAnswerView.as_view()),
    path('lessons/<int:lesson_id>/complete/', CompleteLessonView.as_view()),
    
    # Feedback
    path('questions/<int:pk>/feedback/', QuestionFeedbackView.as_view()),
]
```

### ۲.۲ API Endpoints Summary

| Method | Endpoint | توضیح |
|--------|----------|-------|
| GET | `/api/v1/courses/` | لیست دوره‌ها |
| GET | `/api/v1/courses/{id}/levels/` | سطوح دوره |
| GET | `/api/v1/levels/{id}/juz/` | اجزاء سطح |
| GET | `/api/v1/juz/{id}/` | جزئیات جزء + مراحل |
| GET | `/api/v1/juz/{id}/syllabus/` | درسنامه جزء |
| GET | `/api/v1/juz/{num}/words/` | کلمات جزء (bulk) |
| GET | `/api/v1/stages/{id}/lessons/` | درس‌های مرحله |
| GET | `/api/v1/lessons/{id}/questions/` | سوالات درس |
| GET | `/api/v1/ayah/{global_id}/` | جزئیات آیه |
| GET | `/api/v1/me/progress/` | پیشرفت کاربر |
| GET | `/api/v1/me/lessons/{id}/progress/` | پیشرفت درس |
| POST | `/api/v1/answers/` | ثبت پاسخ |
| POST | `/api/v1/lessons/{id}/complete/` | تکمیل درس |
| POST | `/api/v1/questions/{id}/feedback/` | بازخورد سوال |

### ۲.۳ Sample View Implementation

```python
# apps/api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from infrastructure.bootstrap import get_container

class JuzDetailView(APIView): **HUMAN OVERRIDE**: do not use APIView, but use ViewSet
    """جزئیات جزء"""
    
    def get(self, request, pk):
        container = get_container()
        lesson_service = container.get(LessonService)
        
        juz = lesson_service.get_juz_detail(pk)
        return Response(juz)


class SubmitAnswerView(APIView):
    """ثبت پاسخ"""
    
    def post(self, request):
        container = get_container()
        progress_service = container.get(ProgressService)
        
        result = progress_service.submit_answer( **HUMAN OVERRIDE**: I rather use pydantic for input validation and also contract documentation. I mean we need some request/response models extending BaseModel
            user_id=request.user.id,
            question_id=request.data['question_id'],
            lesson_id=request.data['lesson_id'],
            answer=request.data['answer'],
            is_correct=request.data['is_correct'],
            time_spent_ms=request.data.get('time_spent_ms', 0)
        )
        
        return Response(result)
```

### ۲.۴ Authentication Middleware

```python
# apps/api/middleware.py
from services.auth_service import AuthService
from infrastructure.bootstrap import get_container

class MessengerAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('MessengerToken '):
            token = auth_header[15:]
            container = get_container()
            auth_service = container.get(AuthService)
            
            try:
                user = auth_service.authenticate_messenger_token(token) **HUMAN OVERRIDE**: also pass ip, platform (eitaa/telegram/bale) and mini app sku (now only PEYDA)
                request.user = user
            except Exception:
                pass
        
        return self.get_response(request)
```

---

## ۳. Response Formats

### ۳.۱ Success Response
```json
{
  "id": 1,
  "name": "زبان قرآن",
  "levels": [...]
}
```

### ۳.۲ Error Response
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "جزء مورد نظر یافت نشد",
    "details": {}
  }
}
```

### ۳.۳ Paginated Response
```json
{
  "count": 100,
  "next": "/api/v1/ayahs/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## ۴. Events (رویدادها)

### ۴.۱ Event Types

| Event                                                                                                                                                                    | Publisher       | Payload                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- | ------------------------------------------------------------- |
| `user.created`                                                                                                                                                           | AuthService     | `{user_id, platform, timestamp}`                              |
| `answer.submitted` **HUMAN OVERRIDE**: we dont validate responses in backend. so only complete lessons are available. although we save question id's the user has failed | ProgressService | `{user_id, question_id, lesson_id, is_correct, timestamp}`    |
| `lesson.completed`                                                                                                                                                       | ProgressService | `{user_id, lesson_id, correct_count, wrong_count, timestamp}` |
| `question.feedback`                                                                                                                                                      | QuestionService | `{question_id, user_id, is_positive, timestamp}`              |

### ۴.۲ Event Handlers (n8n Workflows)

```
user.created → Welcome workflow
answer.submitted → Analytics logging
lesson.completed → Achievement check
question.feedback → Quality review queue
```
**HUMAN OVERRIDE**: what does fire n8n? what endpoint it call? what are the main workflows?