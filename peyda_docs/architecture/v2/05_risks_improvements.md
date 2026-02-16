# معماری لِسان v2 - ریسک‌ها، نقاط ضعف و پیشنهادات

## ۱. ریسک‌های امنیتی

### ۱.۱ احراز هویت

| ریسک | شدت | وضعیت فعلی | پیشنهاد |
|------|-----|------------|---------|
| **Replay Attack** | 🟡 متوسط | `auth_date` بررسی می‌شود | ✅ TTL 24 ساعت کافی است |
| **Bot Token Leak** | 🔴 بالا | در env variable | ✅ ولی باید rotate شود |
| **No Rate Limiting** | 🟡 متوسط | پیاده‌سازی نشده | ⚠️ باید اضافه شود |
| **IP Spoofing** | 🟢 پایین | X-Forwarded-For | ✅ قابل قبول پشت reverse proxy |

**اقدام فوری:**
```python
# اضافه کردن rate limiting
# pip install django-ratelimit

from django_ratelimit.decorators import ratelimit

class MessengerAuthMiddleware:
    @ratelimit(key='ip', rate='10/m', block=True)
    def __call__(self, request):
        ...
```

### ۱.۲ Webhook Security

| ریسک | شدت | وضعیت فعلی | پیشنهاد |
|------|-----|------------|---------|
| **Public Webhooks** | 🔴 بالا | مشخص نشده | ⚠️ باید internal-only باشد |
| **No Secret Verification** | 🟡 متوسط | پیاده‌سازی نشده | ⚠️ X-Webhook-Secret اضافه شود |

**اقدام فوری:**
```python
# فقط از شبکه داخلی
ALLOWED_WEBHOOK_IPS = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
```

---

## ۲. باگ‌های احتمالی

### ۲.۱ Race Condition در Progress

**مشکل:**
```python
# اگر کاربر دو بار سریع درس را complete کند
progress, created = LessonProgress.objects.update_or_create(...)
# ممکن است دو رکورد ایجاد شود یا داده‌ها overwrite شوند
```

**راه‌حل:**
```python
from django.db import transaction

@transaction.atomic
def complete_lesson(self, user_id, lesson_id, ...):
    # Lock row for update
    progress = LessonProgress.objects.select_for_update().filter(
        user_id=user_id,
        lesson_id=lesson_id
    ).first()
    
    if progress and progress.status == 'completed':
        # Already completed, return existing data
        return self._build_response(progress)
    
    # ... rest of logic
```

### ۲.۲ N+1 Query در سوالات

**مشکل:**
```python
# در get_lesson_questions
questions = Question.objects.filter(id__in=question_ids)
# سپس loop روی آن‌ها برای حفظ ترتیب
```

**راه‌حل:**
```python
from django.db.models import Case, When

def get_lesson_questions(self, lesson_id: int) -> list[dict]:
    question_ids = list(LessonQuestion.objects.filter(
        lesson_id=lesson_id
    ).order_by('order').values_list('question_id', flat=True))
    
    # Preserve order using Case/When
    preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(question_ids)])
    
    questions = Question.objects.filter(
        id__in=question_ids,
        is_active=True
    ).order_by(preserved_order)
    
    return [self._serialize_question(q) for q in questions]
```

### ۲.۳ Cache Invalidation

**مشکل:**
کش درسنامه و کلمات بعد از تغییر در admin به‌روز نمی‌شود.

**راه‌حل:**
```python
# apps/courses/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from infrastructure.bootstrap import get_container
from infrastructure.cache import Cache

@receiver([post_save, post_delete], sender=Syllabus)
def invalidate_syllabus_cache(sender, instance, **kwargs):
    cache = get_container().get(Cache)
    cache.delete(f"juz:{instance.juz_id}:syllabus")
```

### ۲.۴ RabbitMQ Connection Handling

**مشکل:**
```python
# Connection ممکن است بسته شود و publish fail کند
def publish(self, event_type, payload):
    self._channel.basic_publish(...)  # ممکن است exception بدهد
```

**راه‌حل:**
```python
import pika.exceptions

def publish(self, event_type: str, payload: dict) -> None:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            self._ensure_connection()
            self._channel.basic_publish(...)
            return
        except pika.exceptions.AMQPError as e:
            self._connection = None  # Force reconnect
            if attempt == max_retries - 1:
                logger.error(f"Failed to publish event after {max_retries} attempts: {e}")
                raise
```

---

## ۳. نقاط ضعف معماری

### ۳.۱ عدم وجود CQRS

**وضعیت فعلی:**
سرویس‌ها هم read و هم write انجام می‌دهند.
**HUMAN OVERRIDE**: fix it

**مشکل:**
- پیچیدگی در scale
- سخت برای optimization خواندن جداگانه

**پیشنهاد (V2):**
```
services/
├── commands/              # Write operations
│   ├── complete_lesson.py
│   └── submit_feedback.py
└── queries/               # Read operations
    ├── get_lesson_questions.py
    └── get_user_progress.py
```
**HUMAN OVERRIDE**: proposal accepted
### ۳.۲ Tight Coupling با Django ORM

**وضعیت فعلی:**
سرویس‌ها مستقیماً از ORM استفاده می‌کنند.

**مشکل:**
- تست‌پذیری پایین‌تر
- وابستگی به Django

**پیشنهاد (V2):**
```python
# Repository pattern
class QuestionRepository(ABC):
    @abstractmethod
    def get_by_ids(self, ids: List[int]) -> List[Question]:
        pass

class DjangoQuestionRepository(QuestionRepository):
    def get_by_ids(self, ids: List[int]) -> List[Question]:
        return list(Question.objects.filter(id__in=ids))
```
**HUMAN OVERRIDE**: I accept the risk. leave it.
### ۳.۳ عدم وجود Health Check

**پیشنهاد:**
```python
# apps/api/views/health.py
class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        checks = {
            'database': self._check_database(),
            'rabbitmq': self._check_rabbitmq(),
            'redis': self._check_redis(),
        }
        
        all_healthy = all(checks.values())
        status_code = 200 if all_healthy else 503
        
        return Response({
            'status': 'healthy' if all_healthy else 'unhealthy',
            'checks': checks
        }, status=status_code)
```
**HUMAN OVERRIDE**: do it.

---

## ۴. نقاط ضعف عملیاتی

### ۴.۱ عدم وجود Logging ساختارمند

**پیشنهاد:**
```python
# config/settings/base.py
LOGGING = {
    'version': 1,
    'handlers': {
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        },
    },
    'loggers': {
        'services': {
            'handlers': ['json'],
            'level': 'INFO',
        },
        'events': {
            'handlers': ['json'],
            'level': 'INFO',
        },
    },
}
```
**HUMAN OVERRIDE**: fix it.
### ۴.۲ عدم وجود Metrics

**پیشنهاد:**
```python
# با استفاده از prometheus-client
from prometheus_client import Counter, Histogram

LESSON_COMPLETED = Counter(
    'peyda_lesson_completed_total',
    'Total lessons completed',
    ['juz_number', 'stage_type']
)

LESSON_SCORE = Histogram(
    'peyda_lesson_score',
    'Lesson completion scores',
    buckets=[0, 25, 50, 75, 90, 100]
)
```

### ۴.۳ عدم وجود Backup Strategy

**پیشنهاد:**
```yaml
# docker-compose.yaml
services:
  db-backup:
    image: prodrigestivill/postgres-backup-local
    environment:
      POSTGRES_HOST: db
      POSTGRES_DB: peyda
      SCHEDULE: "@daily"
      BACKUP_KEEP_DAYS: 7
    volumes:
      - ./backups:/backups
```
**HUMAN OVERRIDE**: leave it. k8s will do 

---

## ۵. پیشنهادات بهبود

### ۵.۱ کوتاه‌مدت (Sprint 1-2)

| اولویت | کار | تخمین |
|--------|-----|-------|
| 🔴 | Rate limiting برای auth | 2h |
| 🔴 | Webhook security | 2h |
| 🟡 | Health check endpoint | 1h |
| 🟡 | Cache invalidation signals | 2h |
| 🟡 | RabbitMQ retry logic | 2h |

### ۵.۲ میان‌مدت (Sprint 3-4)

| اولویت | کار | تخمین |
|--------|-----|-------|
| 🟡 | Structured logging | 4h |
| 🟡 | Prometheus metrics | 4h |
| 🟢 | API documentation (OpenAPI) | 4h |
| 🟢 | Integration tests | 8h |

### ۵.۳ بلندمدت (V2)

| کار | مزیت |
|-----|------|
| CQRS pattern | Scalability |
| Repository pattern | Testability |
| Event sourcing | Audit trail |
| GraphQL | Flexible queries |

---

## ۶. Checklist قبل از Production

- [ ] Rate limiting فعال شده
- [ ] Webhook ها secured هستند
- [ ] Bot tokens در env variables هستند
- [ ] Health check endpoint کار می‌کند
- [ ] Logging ساختارمند فعال است
- [ ] Backup خودکار تنظیم شده
- [ ] SSL/TLS فعال است
- [ ] CORS درست تنظیم شده
- [ ] Debug mode غیرفعال است
- [ ] Secret key تولید شده
- [ ] Database connection pooling فعال است
- [ ] Static files در CDN هستند

---

## ۷. Decision Log

| تاریخ | تصمیم | دلیل | Trade-off |
|-------|-------|------|-----------|
| - | Client-side validation | سادگی، UX | قابل تقلب |
| - | ViewSet + Pydantic | مستندسازی، type safety | کمی overhead |
| - | n8n برای workflows | Low-code، سریع | وابستگی به سرویس خارجی |
| - | No subscribe در EventBus | سادگی، n8n handles | کمتر flexible |
| - | FailedQuestion model | تحلیل، مرور | حجم داده بیشتر |
