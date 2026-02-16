# معماری لِسان v2 - یکپارچگی n8n

## ۱. معماری Event-Driven

### ۱.۱ جریان رویدادها

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Django    │     │  RabbitMQ   │     │    n8n      │     │   Django    │
│  (Service)  │     │  (Queue)    │     │ (Workflow)  │     │  (Webhook)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │  1. publish()     │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │  2. consume()     │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │  3. Process       │
       │                   │                   │  workflow         │
       │                   │                   │                   │
       │                   │                   │  4. HTTP POST     │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
```

### ۱.۲ EventBus (فقط Publish)

```python
# infrastructure/event_bus/interface.py
from abc import ABC, abstractmethod

class EventBus(ABC):
    """رابط Event Bus - فقط انتشار"""
    
    @abstractmethod
    def publish(self, event_type: str, payload: dict) -> None:
        """انتشار رویداد به صف"""
        pass
    
    # ❌ حذف شده: subscribe() 
    # n8n مستقیماً از RabbitMQ می‌خواند
```

```python
# infrastructure/event_bus/rabbitmq.py
import json
import pika
from .interface import EventBus

class RabbitMQEventBus(EventBus):
    def __init__(self, connection_url: str):
        self._connection_url = connection_url
        self._connection = None
        self._channel = None
        self._exchange = 'peyda_events'
    
    def _ensure_connection(self):
        if self._connection is None or self._connection.is_closed:
            self._connection = pika.BlockingConnection(
                pika.URLParameters(self._connection_url)
            )
            self._channel = self._connection.channel()
            self._channel.exchange_declare(
                exchange=self._exchange,
                exchange_type='topic',
                durable=True
            )
    
    def publish(self, event_type: str, payload: dict) -> None:
        """انتشار رویداد"""
        self._ensure_connection()
        
        message = json.dumps({
            'event_type': event_type,
            'payload': payload,
            'published_at': payload.get('timestamp')
        })
        
        self._channel.basic_publish(
            exchange=self._exchange,
            routing_key=event_type,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type='application/json'
            )
        )
```

---

## ۲. رویدادهای سیستم

### ۲.۱ لیست رویدادها

| Event | منبع | Payload | n8n Workflow |
|-------|------|---------|--------------|
| `user.created` | AuthService | `{user_id, platform, app_sku, timestamp}` | Welcome Flow |
| `lesson.completed` | ProgressService | `{user_id, lesson_id, score, failed_ids, timestamp}` | Achievement Check |
| `question.feedback` | QuestionService | `{question_id, user_id, is_positive, timestamp}` | Quality Review |
| `question.reported` | QuestionService | `{question_id, user_id, reason, timestamp}` | Report Queue |

### ۲.۲ Payload Schemas

```python
# events/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserCreatedEvent(BaseModel):
    user_id: int
    platform: str
    app_sku: str
    timestamp: datetime

class LessonCompletedEvent(BaseModel):
    user_id: int
    lesson_id: int
    juz_id: int
    stage_id: int
    score: int
    correct_count: int
    wrong_count: int
    failed_question_ids: List[int]
    total_time_ms: int
    timestamp: datetime

class QuestionFeedbackEvent(BaseModel):
    question_id: int
    user_id: int
    is_positive: bool
    timestamp: datetime

class QuestionReportedEvent(BaseModel):
    question_id: int
    user_id: int
    reason: str
    timestamp: datetime
```

---

## ۳. n8n Workflows

### ۳.۱ RabbitMQ Trigger در n8n

```json
{
  "nodes": [
    {
      "name": "RabbitMQ Trigger",
      "type": "n8n-nodes-base.rabbitmqTrigger",
      "parameters": {
        "queue": "peyda_lesson_completed",
        "options": {
          "acknowledge": "immediately"
        }
      }
    }
  ]
}
```

### ۳.۲ Workflow: Welcome (user.created)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  RabbitMQ       │     │  Check if       │     │  POST           │
│  Trigger        │────>│  first user     │────>│  /webhooks/     │
│  user.created   │     │  from platform  │     │  welcome        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Webhook Endpoint:**
```python
# apps/api/webhooks.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class WelcomeWebhook(APIView):
    """Webhook برای ارسال پیام خوش‌آمدگویی"""
    permission_classes = [AllowAny]  # n8n internal only
    
    def post(self, request):
        user_id = request.data['user_id']
        platform = request.data['platform']
        
        # Send welcome message via bot
        # This depends on platform-specific bot API
        
        return Response({'status': 'sent'})
```

### ۳.۳ Workflow: Achievement Check (lesson.completed)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  RabbitMQ       │     │  Check          │     │  POST           │
│  Trigger        │────>│  achievements   │────>│  /webhooks/     │
│  lesson.completed    │  (first lesson,  │     │  achievement    │
└─────────────────┘     │  juz complete)  │     └─────────────────┘
                        └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Update user    │
                        │  XP via API     │
                        └─────────────────┘
```

**Webhook Endpoint:**
```python
class AchievementWebhook(APIView):
    """Webhook برای ثبت دستاورد"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        user_id = request.data['user_id']
        achievement_type = request.data['achievement_type']
        xp_amount = request.data['xp_amount']
        
        # Record achievement
        from apps.progress.models import UserAchievement, UserProgress
        
        UserAchievement.objects.create( **HUMAN OVERRIDE**: no access to domain model in interfaces layer!! it should pass it to service layer
            user_id=user_id,
            achievement_type=achievement_type
        )
        
        UserProgress.objects.filter(user_id=user_id).update(
            total_xp=models.F('total_xp') + xp_amount
        )
        
        return Response({'status': 'recorded'})
```

### ۳.۴ Workflow: Quality Review (question.feedback)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  RabbitMQ       │     │  Aggregate      │     │  IF negative    │
│  Trigger        │────>│  feedback       │────>│  > threshold    │
│  question.feedback   │  count           │     └────────┬────────┘
└─────────────────┘     └─────────────────┘              │
                                                          ▼
                                                   ┌─────────────────┐
                                                   │  POST           │
                                                   │  /webhooks/     │
                                                   │  flag-question  │
                                                   └─────────────────┘
```

### ۳.۵ Workflow: Report Queue (question.reported)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  RabbitMQ       │     │  Create Trello  │     │  Notify admin   │
│  Trigger        │────>│  card / GitHub  │────>│  via Telegram   │
│  question.reported   │  issue           │     │  bot            │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```
**HUMAN OVERRIDE**: all these external call done via n8n itself. but where we save workflows and how to load them?

---

## ۴. Webhook Security

### ۴.۱ Internal-Only Webhooks

```python
# apps/api/middleware.py
class InternalOnlyMiddleware:
    """فقط درخواست‌های داخلی را قبول می‌کند"""
    
    INTERNAL_IPS = ['127.0.0.1', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/webhooks/'):
            client_ip = self._get_client_ip(request)
            if not self._is_internal(client_ip):
                from rest_framework.response import Response
                return Response({'error': 'Forbidden'}, status=403)
        
        return self.get_response(request)
```

### ۴.۲ Webhook Secret (اختیاری)
**HUMAN OVERRIDE**: confirmed. do it

```python
# n8n sends X-Webhook-Secret header
WEBHOOK_SECRET = os.environ.get('N8N_WEBHOOK_SECRET')

class WebhookSecurityMixin:
    def check_webhook_secret(self, request):
        secret = request.META.get('HTTP_X_WEBHOOK_SECRET')
        if secret != WEBHOOK_SECRET:
            raise PermissionDenied("Invalid webhook secret")
```

---

## ۵. RabbitMQ Queue Setup

### ۵.۱ Queue Bindings

```python
# infrastructure/event_bus/setup.py
def setup_queues(channel):
    """ایجاد صف‌ها و binding ها"""
    
    exchange = 'peyda_events'
    
    queues = [
        ('peyda_user_created', 'user.created'),
        ('peyda_lesson_completed', 'lesson.completed'),
        ('peyda_question_feedback', 'question.feedback'),
        ('peyda_question_reported', 'question.reported'),
    ]
    
    for queue_name, routing_key in queues:
        channel.queue_declare(queue=queue_name, durable=True)
        channel.queue_bind(
            exchange=exchange,
            queue=queue_name,
            routing_key=routing_key
        )
```

### ۵.۲ Docker Compose

```yaml
# config/develop/docker-compose.yaml
services:
  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: peyda
      RABBITMQ_DEFAULT_PASS: peyda
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5

  n8n:
    image: n8nio/n8n
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - WEBHOOK_URL=http://api:8000/webhooks/
    ports:
      - "5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - rabbitmq
```

---

## ۶. Monitoring

### ۶.۱ Event Logging

```python
# infrastructure/event_bus/rabbitmq.py
import logging

logger = logging.getLogger('events')

class RabbitMQEventBus(EventBus):
    def publish(self, event_type: str, payload: dict) -> None:
        self._ensure_connection()
        
        logger.info(f"Publishing event: {event_type}", extra={
            'event_type': event_type,
            'payload_keys': list(payload.keys())
        })
        
        # ... publish logic
```

### ۶.۲ Dead Letter Queue

```python
# برای رویدادهایی که پردازش نشدند
def setup_dlq(channel):
    channel.queue_declare(
        queue='peyda_events_dlq',
        durable=True,
        arguments={
            'x-message-ttl': 86400000  # 24 hours
        }
    )
```
