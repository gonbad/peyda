# معماری لِسان v2 - قراردادهای API

## ۱. اصول طراحی

### ۱.۱ ViewSet به جای APIView
استفاده از `ViewSet` برای:
- کاهش boilerplate
- routing خودکار
- یکپارچگی بهتر با DRF

### ۱.۲ Pydantic برای Validation
استفاده از `pydantic` برای:
- اعتبارسنجی ورودی
- مستندسازی قرارداد API
- تولید خودکار OpenAPI schema

---

## ۲. Request/Response Models

### ۲.۱ ساختار فایل‌ها

```
backend/apps/api/
├── __init__.py
├── urls.py
├── viewsets/
│   ├── __init__.py
│   ├── courses.py
│   ├── lessons.py
│   ├── progress.py
│   └── questions.py
└── contracts/
    ├── __init__.py
    ├── base.py
    ├── courses.py
    ├── lessons.py
    ├── progress.py
    └── questions.py
```

### ۲.۲ Base Contracts

```python
# apps/api/contracts/base.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime

class BaseRequest(BaseModel): **HUMAN OVERRIDE**: write requests should have a idempotency key
    """پایه همه Request ها"""
    model_config = ConfigDict(extra='forbid')  # Reject unknown fields


class BaseResponse(BaseModel):
    """پایه همه Response ها"""
    model_config = ConfigDict(from_attributes=True)  # Allow ORM objects


class PaginatedResponse(BaseModel):
    """Response صفحه‌بندی شده"""
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Any]


class ErrorResponse(BaseModel):
    """Response خطا"""
    error: str
    code: str
    details: Optional[dict] = None
```

### ۲.۳ Course Contracts

```python
# apps/api/contracts/courses.py
from pydantic import BaseModel, Field
from typing import Optional, List
from .base import BaseResponse

class CourseResponse(BaseResponse):
    id: int
    name: str
    description: Optional[str] = None


class LevelResponse(BaseResponse):
    id: int
    number: int
    name: str
    focus: Optional[str] = None
    is_active: bool


class JuzResponse(BaseResponse):
    id: int
    number: int
    start_ayah_global_id: int
    end_ayah_global_id: int


class StageResponse(BaseResponse):
    id: int
    hizb_number: Optional[int]
    stage_type: str
    order: int


class JuzDetailResponse(BaseResponse):
    id: int
    number: int
    stages: List[StageResponse]


class LessonResponse(BaseResponse):
    id: int
    order: int
    is_review: bool
    question_count: Optional[int] = None
```

### ۲.۴ Progress Contracts

```python
# apps/api/contracts/progress.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from .base import BaseRequest, BaseResponse

class CompleteLessonRequest(BaseRequest):
    """درخواست تکمیل درس"""
    lesson_id: int = Field(..., gt=0, description="شناسه درس")
    failed_question_ids: List[int] = Field(
        default_factory=list,
        description="لیست شناسه سوالاتی که کاربر اشتباه پاسخ داده"
    )
    total_time_ms: int = Field(
        ..., 
        ge=0, 
        le=3600000,  # Max 1 hour
        description="کل زمان صرف شده (میلی‌ثانیه)"
    )
    
    @field_validator('failed_question_ids')
    @classmethod
    def validate_failed_questions(cls, v):
        if len(v) > 50:  # Sanity check
            raise ValueError('تعداد سوالات اشتباه بیش از حد مجاز')
        return list(set(v))  # Remove duplicates


class CompleteLessonResponse(BaseResponse):
    """پاسخ تکمیل درس"""
    status: str = "completed"
    lesson_id: int
    correct_count: int
    wrong_count: int
    score: int = Field(..., ge=0, le=100)
    xp_earned: int = Field(default=0, ge=0)


class UserProgressResponse(BaseResponse):
    """پیشرفت کلی کاربر"""
    current_juz_id: Optional[int] = None
    current_stage_id: Optional[int] = None
    current_lesson_id: Optional[int] = None
    total_completed_lessons: int = 0
    total_xp: int = 0


class LessonProgressResponse(BaseResponse):
    """پیشرفت درس"""
    lesson_id: int
    status: str  # not_started | in_progress | completed
    correct_count: int = 0
    wrong_count: int = 0
    completed_at: Optional[str] = None
```

### ۲.۵ Question Contracts

```python
# apps/api/contracts/questions.py
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from .base import BaseRequest, BaseResponse

class QuestionResponse(BaseResponse):
    """یک سوال"""
    id: int
    type: str  # matching | fill_blank | sentence_building | multiple_choice
    content: Dict[str, Any]
    difficulty: int = Field(..., ge=1, le=5)


class LessonQuestionsResponse(BaseResponse):
    """سوالات یک درس"""
    lesson_id: int
    questions: List[QuestionResponse]
    total_count: int


class QuestionFeedbackRequest(BaseRequest):
    """درخواست بازخورد سوال"""
    is_positive: bool = Field(..., description="👍 = True, 👎 = False")


class QuestionReportRequest(BaseRequest):
    """درخواست گزارش سوال"""
    reason: str = Field(..., min_length=5, max_length=500)
```

---

## ۳. ViewSets

### ۳.۱ Base ViewSet

```python
# apps/api/viewsets/base.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from pydantic import ValidationError
from infrastructure.bootstrap import get_container
from apps.api.contracts.base import ErrorResponse

class BaseViewSet(viewsets.ViewSet):
    """پایه همه ViewSet ها"""
    permission_classes = [IsAuthenticated]
    
    def get_container(self):
        return get_container()
    
    def validate_request(self, request_model, data):
        """اعتبارسنجی ورودی با Pydantic"""
        try:
            return request_model(**data)
        except ValidationError as e:
            return None, self.validation_error_response(e)
    
    def validation_error_response(self, error: ValidationError):
        """تبدیل خطای Pydantic به Response"""
        return Response(
            ErrorResponse(
                error="Validation Error",
                code="VALIDATION_ERROR",
                details=error.errors()
            ).model_dump(),
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def success_response(self, data, response_model=None):
        """Response موفق با اعتبارسنجی خروجی"""
        if response_model:
            validated = response_model(**data) if isinstance(data, dict) else response_model.model_validate(data)
            return Response(validated.model_dump())
        return Response(data)
    
    def error_response(self, message: str, code: str, status_code: int = 400, details: dict = None):
        """Response خطا"""
        return Response(
            ErrorResponse(error=message, code=code, details=details).model_dump(),
            status=status_code
        )
```

### ۳.۲ Courses ViewSet

```python
# apps/api/viewsets/courses.py
from rest_framework.decorators import action
from rest_framework.response import Response
from services.lesson_service import LessonService
from apps.api.contracts.courses import (
    CourseResponse, LevelResponse, JuzResponse, 
    JuzDetailResponse, LessonResponse, StageResponse
)
from .base import BaseViewSet

class CourseViewSet(BaseViewSet):
    """ViewSet دوره‌ها"""
    
    def list(self, request):
        """GET /api/v1/courses/"""
        service = self.get_container().get(LessonService)
        courses = service.get_courses()
        return Response([CourseResponse(**c).model_dump() for c in courses])
    
    @action(detail=True, methods=['get'], url_path='levels')
    def levels(self, request, pk=None):
        """GET /api/v1/courses/{id}/levels/"""
        service = self.get_container().get(LessonService)
        levels = service.get_levels(int(pk))
        return Response([LevelResponse(**l).model_dump() for l in levels])


class JuzViewSet(BaseViewSet):
    """ViewSet جزء‌ها"""
    
    def retrieve(self, request, pk=None):
        """GET /api/v1/juz/{id}/"""
        service = self.get_container().get(LessonService)
        juz = service.get_juz_detail(int(pk))
        return self.success_response(juz, JuzDetailResponse)
    
    @action(detail=True, methods=['get'])
    def syllabus(self, request, pk=None):
        """GET /api/v1/juz/{id}/syllabus/"""
        service = self.get_container().get(LessonService)
        syllabus = service.get_syllabus(int(pk))
        if not syllabus:
            return self.error_response("Syllabus not found", "NOT_FOUND", 404)
        return Response(syllabus)
    
    @action(detail=True, methods=['get'])
    def lessons(self, request, pk=None):
        """GET /api/v1/juz/{id}/lessons/"""
        # Get all lessons for a juz (across all stages)
        pass


class StageViewSet(BaseViewSet):
    """ViewSet مراحل"""
    
    @action(detail=True, methods=['get'])
    def lessons(self, request, pk=None):
        """GET /api/v1/stages/{id}/lessons/"""
        service = self.get_container().get(LessonService)
        lessons = service.get_stage_lessons(int(pk))
        return Response([LessonResponse(**l).model_dump() for l in lessons])
```

### ۳.۳ Progress ViewSet

```python
# apps/api/viewsets/progress.py
from rest_framework.decorators import action
from services.progress_service import ProgressService
from apps.api.contracts.progress import (
    CompleteLessonRequest, CompleteLessonResponse,
    UserProgressResponse, LessonProgressResponse
)
from .base import BaseViewSet

class ProgressViewSet(BaseViewSet):
    """ViewSet پیشرفت کاربر"""
    
    @action(detail=False, methods=['get'], url_path='me')
    def my_progress(self, request):
        """GET /api/v1/progress/me/"""
        service = self.get_container().get(ProgressService)
        progress = service.get_user_progress(request.user.id)
        return self.success_response(progress, UserProgressResponse)
    
    @action(detail=True, methods=['get'])
    def lesson(self, request, pk=None):
        """GET /api/v1/progress/lesson/{lesson_id}/"""
        service = self.get_container().get(ProgressService)
        progress = service.get_lesson_progress(request.user.id, int(pk))
        return self.success_response(progress, LessonProgressResponse)


class LessonViewSet(BaseViewSet):
    """ViewSet درس‌ها"""
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """GET /api/v1/lessons/{id}/questions/"""
        from services.question_service import QuestionService
        service = self.get_container().get(QuestionService)
        questions = service.get_lesson_questions(int(pk))
        return Response({
            'lesson_id': int(pk),
            'questions': questions,
            'total_count': len(questions)
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """POST /api/v1/lessons/{id}/complete/"""
        
        # Validate request
        try:
            req = CompleteLessonRequest(
                lesson_id=int(pk),
                **request.data
            )
        except Exception as e:
            return self.validation_error_response(e)
        
        # Process completion
        service = self.get_container().get(ProgressService)
        result = service.complete_lesson(
            user_id=request.user.id,
            lesson_id=req.lesson_id,
            failed_question_ids=req.failed_question_ids,
            total_time_ms=req.total_time_ms
        )
        
        return self.success_response(result, CompleteLessonResponse)
```

---

## ۴. URL Routing

```python
# apps/api/urls.py
from rest_framework.routers import DefaultRouter
from .viewsets.courses import CourseViewSet, JuzViewSet, StageViewSet
from .viewsets.progress import ProgressViewSet, LessonViewSet
from .viewsets.questions import QuestionViewSet

router = DefaultRouter()

router.register(r'courses', CourseViewSet, basename='course')
router.register(r'juz', JuzViewSet, basename='juz')
router.register(r'stages', StageViewSet, basename='stage')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'progress', ProgressViewSet, basename='progress')
router.register(r'questions', QuestionViewSet, basename='question')

urlpatterns = router.urls
```

---

## ۵. OpenAPI Schema

با استفاده از Pydantic، می‌توان schema خودکار تولید کرد:

```python
# apps/api/schema.py
from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.utils import extend_schema, OpenApiParameter

# Example usage in viewset:
@extend_schema(
    request=CompleteLessonRequest,
    responses={
        200: CompleteLessonResponse,
        400: ErrorResponse,
        404: ErrorResponse,
    },
    description="تکمیل درس و ثبت نتیجه"
)
@action(detail=True, methods=['post'])
def complete(self, request, pk=None):
    ...
```

---

## ۶. مزایای این رویکرد

| ویژگی | مزیت |
|-------|------|
| **Type Safety** | خطاهای نوع در زمان توسعه شناسایی می‌شوند |
| **Auto Documentation** | مستندات API خودکار تولید می‌شود |
| **Contract Testing** | قراردادها قابل تست هستند |
| **IDE Support** | autocomplete و type hints |
| **Validation** | اعتبارسنجی خودکار ورودی/خروجی |
