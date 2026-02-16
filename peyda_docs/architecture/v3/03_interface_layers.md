# معماری لِسان v3 - لایه‌های Interface

## ۱. مفهوم Interface Layer

Interface Layer نقطه ورود به سیستم است و **فقط** وظایف زیر را دارد:
- دریافت درخواست
- اعتبارسنجی ورودی (با Pydantic)
- فراخوانی Command یا Query مناسب
- برگرداندن پاسخ

**⚠️ قانون مهم:** Interface Layer **هرگز** مستقیماً به Domain Model دسترسی ندارد!

```
┌─────────────────────────────────────────────────────────────────┐
│                      INTERFACE LAYER                            │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│   REST API      │  n8n Handlers   │  Bot Webhook    │  Signals  │
│   (ViewSets)    │  (Internal)     │  (External)     │  (Django) │
└────────┬────────┴────────┬────────┴────────┬────────┴─────┬─────┘
         │                 │                 │              │
         └─────────────────┴─────────────────┴──────────────┘
                                   │
                                   ▼
         ┌─────────────────────────────────────────────────────────┐
         │                   APPLICATION LAYER                      │
         │              (Commands / Queries / Services)             │
         └─────────────────────────────────────────────────────────┘
```

---

## ۲. ساختار فایل‌ها

```
backend/
├── apps/
│   ├── api/                          # REST API Interface
│   │   ├── authentication.py
│   │   ├── permissions.py
│   │   ├── contracts/
│   │   │   ├── base.py
│   │   │   ├── courses.py
│   │   │   └── progress.py
│   │   ├── viewsets/
│   │   │   ├── base.py
│   │   │   ├── courses.py
│   │   │   └── progress.py
│   │   └── urls.py
│   │
│   ├── webhooks/                     # n8n Handlers Interface
│   │   ├── authentication.py         # Webhook secret verification
│   │   ├── contracts/
│   │   │   ├── notifications.py
│   │   │   └── achievements.py
│   │   ├── handlers/
│   │   │   ├── base.py
│   │   │   ├── notifications.py
│   │   │   └── achievements.py
│   │   └── urls.py
│   │
│   ├── bot/                          # Bot Webhook Interface
│   │   ├── authentication.py         # Bot signature verification
│   │   ├── state/                    # State management
│   │   │   ├── base.py
│   │   │   └── redis_state.py
│   │   ├── handlers/
│   │   │   ├── base.py
│   │   │   ├── commands.py
│   │   │   └── callbacks.py
│   │   └── urls.py
│   │
│   └── signals/                      # Django Signals Interface
│       ├── handlers/
│       │   ├── cache_invalidation.py
│       │   └── audit_log.py
│       └── registry.py
```

---

## ۳. REST API Interface

### ۳.۱ Base ViewSet

```python
# apps/api/viewsets/base.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from pydantic import ValidationError
from infrastructure.bootstrap import get_container
from apps.api.contracts.base import ErrorResponse
import time

class BaseViewSet(viewsets.ViewSet):
    """پایه همه ViewSet ها"""
    
    def get_container(self):
        return get_container()
    
    def get_command(self, command_class):
        """دریافت Command از container"""
        return self.get_container().get(command_class)
    
    def get_query(self, query_class):
        """دریافت Query از container"""
        return self.get_container().get(query_class)
    
    def validate_request(self, request_model, data):
        """اعتبارسنجی با Pydantic"""
        try:
            return request_model(**data), None
        except ValidationError as e:
            return None, self.validation_error(e)
    
    def validation_error(self, error):
        return Response(
            ErrorResponse(
                error="Validation Error",
                code="VALIDATION_ERROR",
                details={'errors': error.errors()}
            ).model_dump(),
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def success(self, data, response_model=None):
        if response_model:
            validated = response_model.model_validate(data) if hasattr(data, '__dict__') else response_model(**data)
            return Response(validated.model_dump())
        return Response(data)
    
    def error(self, message: str, code: str, status_code: int = 400):
        return Response(
            ErrorResponse(error=message, code=code).model_dump(),
            status=status_code
        )
```

### ۳.۲ Progress ViewSet

```python
# apps/api/viewsets/progress.py
from rest_framework.decorators import action
from apps.api.contracts.progress import (
    CompleteLessonRequest, CompleteLessonResponse
)
from apps.api.decorators import idempotent
from services.commands.complete_lesson import CompleteLessonCommand
from services.queries.get_user_progress import GetUserProgressQuery
from .base import BaseViewSet

class LessonViewSet(BaseViewSet):
    
    @action(detail=True, methods=['post'])
    @idempotent
    def complete(self, request, pk=None):
        """POST /api/v1/lessons/{id}/complete/"""
        
        # 1. Validate input
        req, error = self.validate_request(CompleteLessonRequest, {
            **request.data,
            'idempotency_key': request.data.get('idempotency_key') or 
                              request.META.get('HTTP_X_IDEMPOTENCY_KEY')
        })
        if error:
            return error
        
        # 2. Execute command
        command = self.get_command(CompleteLessonCommand)
        result = command.execute(
            user_id=request.user.id,
            lesson_id=int(pk),
            failed_question_ids=req.failed_question_ids,
            total_time_ms=req.total_time_ms,
            client_timestamp=req.client_timestamp
        )
        
        # 3. Return response
        return self.success(result, CompleteLessonResponse)
```

---

## ۴. n8n Handlers Interface

### ۴.۱ Webhook Authentication

```python
# apps/webhooks/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import hmac

class WebhookSecretAuthentication(BaseAuthentication):
    """احراز هویت با X-Webhook-Secret"""
    
    def authenticate(self, request):
        secret = request.META.get('HTTP_X_WEBHOOK_SECRET')
        
        if not secret:
            raise AuthenticationFailed('Missing webhook secret')
        
        if not hmac.compare_digest(secret, settings.N8N_WEBHOOK_SECRET):
            raise AuthenticationFailed('Invalid webhook secret')
        
        # Return None for user (no user in webhook context)
        return (None, {'source': 'n8n'})
```

### ۴.۲ Base Handler

```python
# apps/webhooks/handlers/base.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pydantic import ValidationError
from apps.webhooks.authentication import WebhookSecretAuthentication
from infrastructure.bootstrap import get_container

class BaseWebhookHandler(APIView):
    """پایه همه Webhook Handler ها"""
    
    authentication_classes = [WebhookSecretAuthentication]
    permission_classes = []  # No permission needed after auth
    
    def get_container(self):
        return get_container()
    
    def get_command(self, command_class):
        return self.get_container().get(command_class)
    
    def validate(self, request_model, data):
        try:
            return request_model(**data), None
        except ValidationError as e:
            return None, Response(
                {'error': 'Validation Error', 'details': e.errors()},
                status=status.HTTP_400_BAD_REQUEST
            )
```

### ۴.۳ Notification Result Handler

```python
# apps/webhooks/handlers/notifications.py
from rest_framework.response import Response
from apps.api.contracts.notifications import (
    SaveNotificationResultRequest,
    SaveNotificationResultResponse
)
from services.commands.save_notification_result import SaveNotificationResultCommand
from .base import BaseWebhookHandler

class SaveNotificationResultHandler(BaseWebhookHandler):
    """ذخیره نتیجه ارسال نوتیفیکیشن از n8n"""
    
    def post(self, request):
        # 1. Validate
        req, error = self.validate(SaveNotificationResultRequest, request.data)
        if error:
            return error
        
        # 2. Execute command (NOT direct model access!)
        command = self.get_command(SaveNotificationResultCommand)
        result = command.execute(
            notification_id=req.notification_id,
            user_id=req.user_id,
            channel=req.channel,
            template=req.template,
            status=req.status,
            platform_message_id=req.platform_message_id,
            error_message=req.error_message,
            sent_at=req.sent_at,
            metadata=req.metadata
        )
        
        # 3. Return
        return Response(
            SaveNotificationResultResponse(
                notification_id=req.notification_id,
                saved=True
            ).model_dump()
        )
```

### ۴.۴ Achievement Handler

```python
# apps/webhooks/handlers/achievements.py
from services.commands.grant_achievement import GrantAchievementCommand
from .base import BaseWebhookHandler

class GrantAchievementHandler(BaseWebhookHandler):
    """ثبت دستاورد کاربر از n8n"""
    
    def post(self, request):
        # Validate
        user_id = request.data.get('user_id')
        achievement_type = request.data.get('achievement_type')
        xp_amount = request.data.get('xp_amount', 0)
        
        # Execute command (NOT direct model access!)
        command = self.get_command(GrantAchievementCommand)
        command.execute(
            user_id=user_id,
            achievement_type=achievement_type,
            xp_amount=xp_amount
        )
        
        return Response({'status': 'granted'})
```

### ۴.۵ Webhook URLs

```python
# apps/webhooks/urls.py
from django.urls import path
from .handlers.notifications import SaveNotificationResultHandler
from .handlers.achievements import GrantAchievementHandler

urlpatterns = [
    path('notification-result/', SaveNotificationResultHandler.as_view()),
    path('achievement/', GrantAchievementHandler.as_view()),
]
```

---

## ۵. Bot Webhook Interface

### ۵.۱ State Management

```python
# apps/bot/state/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BotState(ABC):
    """رابط مدیریت state برای bot"""
    
    @abstractmethod
    def get(self, user_id: str, platform: str) -> Optional[Dict[str, Any]]:
        """دریافت state کاربر"""
        pass
    
    @abstractmethod
    def set(self, user_id: str, platform: str, state: Dict[str, Any], ttl: int = 3600) -> None:
        """ذخیره state کاربر"""
        pass
    
    @abstractmethod
    def delete(self, user_id: str, platform: str) -> None:
        """حذف state کاربر"""
        pass
```

```python
# apps/bot/state/redis_state.py
import json
from typing import Optional, Dict, Any
from infrastructure.cache import Cache
from .base import BotState

class RedisBotState(BotState):
    """پیاده‌سازی State با Redis"""
    
    def __init__(self, cache: Cache):
        self._cache = cache
    
    def _key(self, user_id: str, platform: str) -> str:
        return f"bot:state:{platform}:{user_id}"
    
    def get(self, user_id: str, platform: str) -> Optional[Dict[str, Any]]:
        data = self._cache.get(self._key(user_id, platform))
        return json.loads(data) if data else None
    
    def set(self, user_id: str, platform: str, state: Dict[str, Any], ttl: int = 3600) -> None:
        self._cache.set(
            self._key(user_id, platform),
            json.dumps(state),
            ttl=ttl
        )
    
    def delete(self, user_id: str, platform: str) -> None:
        self._cache.delete(self._key(user_id, platform))
```

### ۵.۲ Bot Handler Base

```python
# apps/bot/handlers/base.py
from rest_framework.views import APIView
from rest_framework.response import Response
from infrastructure.bootstrap import get_container
from apps.bot.state.base import BotState

class BaseBotHandler(APIView):
    """پایه Handler های بات"""
    
    permission_classes = []  # Bot verifies signature differently
    
    def get_container(self):
        return get_container()
    
    def get_state(self) -> BotState:
        return self.get_container().get(BotState)
    
    def get_command(self, command_class):
        return self.get_container().get(command_class)
    
    def verify_signature(self, request, platform: str) -> bool:
        """اعتبارسنجی امضای پلتفرم"""
        # Each platform has different signature verification
        raise NotImplementedError
```

### ۵.۳ Telegram/Eitaa Bot Handler

```python
# apps/bot/handlers/telegram.py
import hmac
import hashlib
from django.conf import settings
from rest_framework.response import Response
from services.commands.handle_bot_message import HandleBotMessageCommand
from .base import BaseBotHandler

class TelegramBotHandler(BaseBotHandler):
    """Handler برای Telegram/Eitaa bot webhook"""
    
    def post(self, request, platform: str):
        # 1. Verify signature
        if not self.verify_signature(request, platform):
            return Response({'error': 'Invalid signature'}, status=403)
        
        # 2. Parse update
        update = request.data
        
        # 3. Get user state
        state_manager = self.get_state()
        user_id = str(self._get_user_id(update))
        current_state = state_manager.get(user_id, platform)
        
        # 4. Execute command
        command = self.get_command(HandleBotMessageCommand)
        result = command.execute(
            platform=platform,
            update=update,
            current_state=current_state
        )
        
        # 5. Update state if needed
        if result.get('new_state'):
            state_manager.set(user_id, platform, result['new_state'])
        elif result.get('clear_state'):
            state_manager.delete(user_id, platform)
        
        # 6. Return response for bot API
        return Response(result.get('response', {'ok': True}))
    
    def verify_signature(self, request, platform: str) -> bool:
        secret_token = request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN')
        expected = settings.BOT_WEBHOOK_SECRETS.get(platform)
        
        if not secret_token or not expected:
            return False
        
        return hmac.compare_digest(secret_token, expected)
    
    def _get_user_id(self, update: dict) -> int:
        if 'message' in update:
            return update['message']['from']['id']
        if 'callback_query' in update:
            return update['callback_query']['from']['id']
        return 0
```

---

## ۶. Django Signals Interface

### ۶.۱ Signal Handler Registry

```python
# apps/signals/registry.py
from django.apps import AppConfig

class SignalsConfig(AppConfig):
    name = 'apps.signals'
    
    def ready(self):
        # Import handlers to register them
        from . import handlers  # noqa
```

### ۶.۲ Cache Invalidation Handler

```python
# apps/signals/handlers/cache_invalidation.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from infrastructure.bootstrap import get_container
from apps.courses.models import Syllabus, Lesson, Question

@receiver([post_save, post_delete], sender=Syllabus)
def invalidate_syllabus_cache(sender, instance, **kwargs):
    """Invalidate cache when syllabus changes"""
    from services.commands.invalidate_cache import InvalidateCacheCommand
    
    container = get_container()
    command = container.get(InvalidateCacheCommand)
    command.execute(cache_key=f"juz:{instance.juz_id}:syllabus")


@receiver([post_save, post_delete], sender=Question)
def invalidate_question_cache(sender, instance, **kwargs):
    """Invalidate cache when question changes"""
    from services.commands.invalidate_cache import InvalidateCacheCommand
    
    container = get_container()
    command = container.get(InvalidateCacheCommand)
    command.execute(cache_key=f"question:{instance.id}")
```

### ۶.۳ Audit Log Handler

```python
# apps/signals/handlers/audit_log.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from infrastructure.bootstrap import get_container

@receiver(post_save, sender=LogEntry)
def log_admin_action(sender, instance, created, **kwargs):
    """Log admin actions to event bus"""
    if not created:
        return
    
    from services.commands.log_admin_action import LogAdminActionCommand
    
    container = get_container()
    command = container.get(LogAdminActionCommand)
    command.execute(
        user_id=instance.user_id,
        action_flag=instance.action_flag,
        content_type_id=instance.content_type_id,
        object_id=instance.object_id,
        object_repr=instance.object_repr,
        change_message=instance.change_message
    )
```

---

## ۷. URL Configuration

```python
# config/urls.py
from django.urls import path, include

urlpatterns = [
    # REST API
    path('api/v1/', include('apps.api.urls')),
    
    # n8n Webhooks (internal)
    path('webhooks/', include('apps.webhooks.urls')),
    
    # Bot Webhooks (external platforms)
    path('bot/<str:platform>/', include('apps.bot.urls')),
    
    # Admin
    path('admin/', admin.site.urls),
]
```

---

## ۸. خلاصه قواعد

| Interface | Authentication | Model Access | State |
|-----------|---------------|--------------|-------|
| REST API | InitData | ❌ via Command/Query | Stateless |
| n8n Handlers | Webhook Secret | ❌ via Command | Stateless |
| Bot Webhook | Platform Signature | ❌ via Command | Redis |
| Signals | N/A (internal) | ❌ via Command | N/A |

**قانون طلایی:** Interface ها فقط Command/Query صدا می‌زنند، هرگز مستقیم به Model دسترسی ندارند!
