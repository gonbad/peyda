# معماری لِسان v3 - قراردادهای API

## ۱. قواعد کلی

### ۱.۱ Unix Timestamp برای DateTime
**همه** تاریخ/زمان‌ها در ارتباط frontend ↔ backend ↔ n8n به صورت **Unix timestamp (ثانیه)** هستند.

```python
# ❌ نادرست
{"completed_at": "2024-01-15T14:30:00Z"}

# ✅ درست
{"completed_at": 1705329000}
```

### ۱.۲ Idempotency Key برای Write Operations
هر درخواست write باید یک `idempotency_key` داشته باشد تا از duplicate جلوگیری شود.

```python
# Header
X-Idempotency-Key: <uuid4>

# یا در body
{"idempotency_key": "550e8400-e29b-41d4-a716-446655440000", ...}
```

---

## ۲. Base Contracts

```python
# apps/api/contracts/base.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Any, TypeVar
from uuid import UUID
import time

T = TypeVar('T')


class BaseRequest(BaseModel):
    """پایه همه Request ها"""
    model_config = ConfigDict(extra='forbid')


class WriteRequest(BaseRequest):
    """پایه درخواست‌های Write (نیاز به idempotency_key)"""
    idempotency_key: UUID = Field(
        ...,
        description="کلید یکتا برای جلوگیری از درخواست تکراری"
    )


class BaseResponse(BaseModel):
    """پایه همه Response ها"""
    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """Mixin برای فیلدهای زمانی"""
    created_at: int = Field(..., description="Unix timestamp (seconds)")
    updated_at: Optional[int] = Field(None, description="Unix timestamp (seconds)")


class PaginatedResponse(BaseModel):
    """Response صفحه‌بندی شده"""
    count: int
    next_cursor: Optional[str] = None
    results: List[Any]


class ErrorResponse(BaseModel):
    """Response خطا"""
    error: str
    code: str
    details: Optional[dict] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))


class SuccessResponse(BaseModel):
    """Response موفق ساده"""
    success: bool = True
    timestamp: int = Field(default_factory=lambda: int(time.time()))
```

---

## ۳. Idempotency Implementation

### ۳.۱ Model

```python
# apps/api/models.py
from django.db import models

class IdempotencyRecord(models.Model):
    """ذخیره نتیجه درخواست‌های idempotent"""
    
    key = models.UUIDField(unique=True, db_index=True)
    user_id = models.PositiveIntegerField(db_index=True)
    endpoint = models.CharField(max_length=200)
    
    # Response ذخیره شده
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['key', 'user_id']),
            models.Index(fields=['created_at']),  # برای cleanup
        ]
```

### ۳.۲ Decorator

```python
# apps/api/decorators.py
from functools import wraps
from rest_framework.response import Response
from apps.api.models import IdempotencyRecord
from django.db import transaction
import hashlib

def idempotent(func):
    """Decorator برای endpoint های idempotent"""
    
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        # Get idempotency key from header or body
        idem_key = (
            request.META.get('HTTP_X_IDEMPOTENCY_KEY') or
            request.data.get('idempotency_key')
        )
        
        if not idem_key:
            return Response(
                {'error': 'Missing idempotency_key', 'code': 'IDEMPOTENCY_REQUIRED'},
                status=400
            )
        
        user_id = request.user.id
        endpoint = f"{request.method}:{request.path}"
        
        # Check for existing response
        existing = IdempotencyRecord.objects.filter(
            key=idem_key,
            user_id=user_id
        ).first()
        
        if existing:
            return Response(
                existing.response_body,
                status=existing.response_status
            )
        
        # Execute and store
        with transaction.atomic():
            response = func(self, request, *args, **kwargs)
            
            IdempotencyRecord.objects.create(
                key=idem_key,
                user_id=user_id,
                endpoint=endpoint,
                response_status=response.status_code,
                response_body=response.data
            )
            
            return response
    
    return wrapper
```

### ۳.۳ Usage in ViewSet

```python
# apps/api/viewsets/lessons.py
from apps.api.decorators import idempotent

class LessonViewSet(BaseViewSet):
    
    @action(detail=True, methods=['post'])
    @idempotent
    def complete(self, request, pk=None):
        """POST /api/v1/lessons/{id}/complete/"""
        # ... completion logic
```

### ۳.۴ Cleanup Job

```python
# management/commands/cleanup_idempotency.py
from django.core.management.base import BaseCommand
from apps.api.models import IdempotencyRecord
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **options):
        # حذف رکوردهای قدیمی‌تر از ۲۴ ساعت
        cutoff = timezone.now() - timedelta(hours=24)
        deleted, _ = IdempotencyRecord.objects.filter(
            created_at__lt=cutoff
        ).delete()
        self.stdout.write(f"Deleted {deleted} old idempotency records")
```

---

## ۴. Progress Contracts (با Unix Timestamp)

```python
# apps/api/contracts/progress.py
from pydantic import Field
from typing import List, Optional
from uuid import UUID
from .base import WriteRequest, BaseResponse

class CompleteLessonRequest(WriteRequest):
    """درخواست تکمیل درس"""
    failed_question_ids: List[int] = Field(
        default_factory=list,
        description="شناسه سوالات اشتباه"
    )
    total_time_ms: int = Field(
        ..., 
        ge=0, 
        le=3600000,
        description="زمان کل (میلی‌ثانیه)"
    )
    client_timestamp: int = Field(
        ...,
        description="Unix timestamp زمان تکمیل در کلاینت"
    )


class CompleteLessonResponse(BaseResponse):
    """پاسخ تکمیل درس"""
    lesson_id: int
    correct_count: int
    wrong_count: int
    score: int = Field(..., ge=0, le=100)
    xp_earned: int = Field(default=0, ge=0)
    completed_at: int  # Unix timestamp


class UserProgressResponse(BaseResponse):
    """پیشرفت کلی کاربر"""
    current_juz_id: Optional[int] = None
    current_stage_id: Optional[int] = None
    current_lesson_id: Optional[int] = None
    total_completed_lessons: int = 0
    total_xp: int = 0
    last_activity_at: Optional[int] = None  # Unix timestamp


class LessonProgressResponse(BaseResponse):
    """پیشرفت درس"""
    lesson_id: int
    status: str
    correct_count: int = 0
    wrong_count: int = 0
    completed_at: Optional[int] = None  # Unix timestamp
```

---

## ۵. Question Contracts

```python
# apps/api/contracts/questions.py
from pydantic import Field
from typing import List, Dict, Any
from uuid import UUID
from .base import WriteRequest, BaseResponse

class QuestionResponse(BaseResponse):
    """یک سوال"""
    id: int
    type: str
    content: Dict[str, Any]
    difficulty: int = Field(..., ge=1, le=5)


class LessonQuestionsResponse(BaseResponse):
    """سوالات یک درس"""
    lesson_id: int
    questions: List[QuestionResponse]
    total_count: int


class QuestionFeedbackRequest(WriteRequest):
    """بازخورد سوال"""
    is_positive: bool


class QuestionReportRequest(WriteRequest):
    """گزارش سوال"""
    reason: str = Field(..., min_length=5, max_length=500)
```

---

## ۶. Notification Contracts (جدید)

```python
# apps/api/contracts/notifications.py
from pydantic import Field
from typing import Optional, Dict, Any
from uuid import UUID
from .base import WriteRequest, BaseResponse

class SaveNotificationResultRequest(WriteRequest):
    """ذخیره نتیجه ارسال نوتیفیکیشن (از n8n)"""
    notification_id: UUID
    user_id: int
    channel: str = Field(..., description="eitaa | telegram | bale | sms")
    template: str = Field(..., description="نام template پیام")
    
    # Result
    status: str = Field(..., description="sent | failed | blocked")
    platform_message_id: Optional[str] = Field(None, description="شناسه پیام در پلتفرم")
    error_message: Optional[str] = None
    
    # Timing
    sent_at: int  # Unix timestamp
    
    # Extra data
    metadata: Optional[Dict[str, Any]] = None


class SaveNotificationResultResponse(BaseResponse):
    """پاسخ ذخیره نتیجه نوتیفیکیشن"""
    notification_id: UUID
    saved: bool = True
```

---

## ۷. Datetime Conversion Utilities

```python
# utils/datetime.py
from datetime import datetime
from typing import Optional

def to_unix(dt: Optional[datetime]) -> Optional[int]:
    """Convert datetime to Unix timestamp"""
    if dt is None:
        return None
    return int(dt.timestamp())


def from_unix(ts: Optional[int]) -> Optional[datetime]:
    """Convert Unix timestamp to datetime"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)


# Usage in serialization
class LessonProgressSerializer:
    def to_response(self, progress) -> LessonProgressResponse:
        return LessonProgressResponse(
            lesson_id=progress.lesson_id,
            status=progress.status,
            correct_count=progress.correct_count,
            wrong_count=progress.wrong_count,
            completed_at=to_unix(progress.completed_at)
        )
```

---

## ۸. Frontend Integration

```typescript
// frontend/src/api/types.ts

interface CompleteLessonRequest {
  idempotency_key: string;  // uuid v4
  failed_question_ids: number[];
  total_time_ms: number;
  client_timestamp: number;  // Date.now() / 1000
}

interface CompleteLessonResponse {
  lesson_id: number;
  correct_count: number;
  wrong_count: number;
  score: number;
  xp_earned: number;
  completed_at: number;  // Unix timestamp
}

// Usage
const request: CompleteLessonRequest = {
  idempotency_key: crypto.randomUUID(),
  failed_question_ids: [2, 5],
  total_time_ms: 180000,
  client_timestamp: Math.floor(Date.now() / 1000)
};
```
