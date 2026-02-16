# معماری لِسان v3 - n8n Workflows

## ۱. ذخیره و بارگذاری Workflow ها

### ۱.۱ ساختار فایل‌ها

```
infrastructure/
└── n8n/
    ├── workflows/                    # Workflow definitions (JSON)
    │   ├── user_welcome.json
    │   ├── lesson_completed.json
    │   ├── achievement_check.json
    │   ├── question_feedback.json
    │   └── question_reported.json
    ├── credentials/                  # Credential templates
    │   ├── rabbitmq.json
    │   └── webhook.json
    ├── export.py                     # Export from n8n
    ├── import.py                     # Import to n8n
    └── README.md                     # Documentation
```

### ۱.۲ Workflow Export Script

```python
# infrastructure/n8n/export.py
"""
Export workflows from n8n to JSON files for version control.
Run this after making changes in n8n GUI.
"""
import requests
import json
import os
from pathlib import Path

N8N_URL = os.environ.get('N8N_URL', 'http://localhost:5678')
N8N_API_KEY = os.environ.get('N8N_API_KEY')

WORKFLOWS_DIR = Path(__file__).parent / 'workflows'

def export_workflows():
    """Export all workflows from n8n"""
    
    headers = {'X-N8N-API-KEY': N8N_API_KEY}
    
    # Get all workflows
    response = requests.get(f'{N8N_URL}/api/v1/workflows', headers=headers)
    workflows = response.json()['data']
    
    for workflow in workflows:
        workflow_id = workflow['id']
        name = workflow['name'].lower().replace(' ', '_')
        
        # Get full workflow
        detail = requests.get(
            f'{N8N_URL}/api/v1/workflows/{workflow_id}',
            headers=headers
        ).json()
        
        # Remove runtime fields
        detail.pop('id', None)
        detail.pop('createdAt', None)
        detail.pop('updatedAt', None)
        
        # Save to file
        filepath = WORKFLOWS_DIR / f'{name}.json'
        with open(filepath, 'w') as f:
            json.dump(detail, f, indent=2, ensure_ascii=False)
        
        print(f'Exported: {name}')

if __name__ == '__main__':
    export_workflows()
```

### ۱.۳ Workflow Import Script

```python
# infrastructure/n8n/import.py
"""
Import workflows from JSON files to n8n.
Run this when deploying to new environment.
"""
import requests
import json
import os
from pathlib import Path

N8N_URL = os.environ.get('N8N_URL', 'http://localhost:5678')
N8N_API_KEY = os.environ.get('N8N_API_KEY')

WORKFLOWS_DIR = Path(__file__).parent / 'workflows'

def import_workflows():
    """Import all workflows to n8n"""
    
    headers = {
        'X-N8N-API-KEY': N8N_API_KEY,
        'Content-Type': 'application/json'
    }
    
    for filepath in WORKFLOWS_DIR.glob('*.json'):
        with open(filepath) as f:
            workflow = json.load(f)
        
        # Check if exists
        existing = requests.get(
            f'{N8N_URL}/api/v1/workflows',
            headers=headers,
            params={'name': workflow['name']}
        ).json()
        
        if existing['data']:
            # Update existing
            workflow_id = existing['data'][0]['id']
            requests.patch(
                f'{N8N_URL}/api/v1/workflows/{workflow_id}',
                headers=headers,
                json=workflow
            )
            print(f'Updated: {workflow["name"]}')
        else:
            # Create new
            requests.post(
                f'{N8N_URL}/api/v1/workflows',
                headers=headers,
                json=workflow
            )
            print(f'Created: {workflow["name"]}')

if __name__ == '__main__':
    import_workflows()
```

### ۱.۴ Deployment Integration

```yaml
# config/develop/docker-compose.yaml
services:
  n8n:
    image: n8nio/n8n
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_API_KEY=${N8N_API_KEY}
    volumes:
      - n8n_data:/home/node/.n8n
      - ./../../infrastructure/n8n/workflows:/workflows:ro
    # Import workflows on startup
    command: >
      sh -c "
        n8n start &
        sleep 10 &&
        python /app/import_workflows.py &&
        wait
      "
```

---

## ۲. Notification Logging

### ۲.۱ Notification Model

```python
# apps/notifications/models.py
from django.db import models
import uuid

class Notification(models.Model):
    """لاگ نوتیفیکیشن‌های ارسال شده"""
    
    class Channel(models.TextChoices):
        EITAA = 'eitaa', 'ایتا'
        TELEGRAM = 'telegram', 'تلگرام'
        BALE = 'bale', 'بله'
        SMS = 'sms', 'پیامک'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        SENT = 'sent', 'ارسال شده'
        FAILED = 'failed', 'ناموفق'
        BLOCKED = 'blocked', 'بلاک شده'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.PositiveIntegerField(db_index=True)
    
    # What
    template = models.CharField(max_length=100, db_index=True)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    payload = models.JSONField(default=dict, help_text="پارامترهای template")
    
    # Result
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    platform_message_id = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        help_text="شناسه پیام در پلتفرم"
    )
    error_message = models.TextField(null=True, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Extra
    metadata = models.JSONField(default=dict)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['created_at']),
        ]
```

### ۲.۲ Save Notification Result Command

```python
# services/commands/save_notification_result.py
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from apps.notifications.models import Notification
from .base import BaseCommand

class SaveNotificationResultCommand(BaseCommand):
    """ذخیره نتیجه ارسال نوتیفیکیشن از n8n"""
    
    def execute(
        self,
        notification_id: UUID,
        user_id: int,
        channel: str,
        template: str,
        status: str,
        platform_message_id: Optional[str],
        error_message: Optional[str],
        sent_at: int,  # Unix timestamp
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        
        # Get or create notification
        notification, created = Notification.objects.update_or_create(
            id=notification_id,
            defaults={
                'user_id': user_id,
                'channel': channel,
                'template': template,
                'status': status,
                'platform_message_id': platform_message_id,
                'error_message': error_message,
                'sent_at': datetime.fromtimestamp(sent_at),
                'metadata': metadata or {}
            }
        )
        
        # Log for monitoring
        self._logger.info(
            f"Notification {status}",
            extra={
                'notification_id': str(notification_id),
                'user_id': user_id,
                'channel': channel,
                'template': template,
                'status': status
            }
        )
        
        return {
            'notification_id': notification_id,
            'saved': True,
            'created': created
        }
```

---

## ۳. Workflow Definitions

### ۳.۱ User Welcome Workflow

```json
{
  "name": "User Welcome",
  "nodes": [
    {
      "name": "RabbitMQ Trigger",
      "type": "n8n-nodes-base.rabbitmqTrigger",
      "parameters": {
        "queue": "peyda_user_created",
        "options": {"acknowledge": "immediately"}
      },
      "position": [250, 300]
    },
    {
      "name": "Prepare Message",
      "type": "n8n-nodes-base.set",
      "parameters": {
        "values": {
          "string": [
            {
              "name": "message",
              "value": "سلام! 👋 به لِسان خوش آمدی.\n\nبرای شروع یادگیری قرآن، روی دکمه زیر بزن:"
            }
          ]
        }
      },
      "position": [450, 300]
    },
    {
      "name": "Send via Platform",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "dataPropertyName": "={{$json.payload.platform}}",
        "rules": [
          {"value": "eitaa"},
          {"value": "telegram"},
          {"value": "bale"}
        ]
      },
      "position": [650, 300]
    },
    {
      "name": "Send Eitaa",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://eitaayar.ir/api/bot{{$credentials.eitaa_token}}/sendMessage",
        "method": "POST",
        "body": {
          "chat_id": "={{$json.payload.platform_user_id}}",
          "text": "={{$node['Prepare Message'].json.message}}"
        }
      },
      "position": [850, 200]
    },
    {
      "name": "Save Result",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{$env.BACKEND_URL}}/webhooks/notification-result/",
        "method": "POST",
        "headers": {
          "X-Webhook-Secret": "={{$env.WEBHOOK_SECRET}}"
        },
        "body": {
          "idempotency_key": "={{$json.notification_id}}",
          "notification_id": "={{$json.notification_id}}",
          "user_id": "={{$json.payload.user_id}}",
          "channel": "={{$json.payload.platform}}",
          "template": "welcome",
          "status": "={{$json.ok ? 'sent' : 'failed'}}",
          "platform_message_id": "={{$json.result?.message_id}}",
          "error_message": "={{$json.description}}",
          "sent_at": "={{Math.floor(Date.now()/1000)}}"
        }
      },
      "position": [1050, 300]
    }
  ],
  "connections": {
    "RabbitMQ Trigger": {"main": [[{"node": "Prepare Message", "type": "main", "index": 0}]]},
    "Prepare Message": {"main": [[{"node": "Send via Platform", "type": "main", "index": 0}]]},
    "Send via Platform": {
      "main": [
        [{"node": "Send Eitaa", "type": "main", "index": 0}],
        [{"node": "Send Telegram", "type": "main", "index": 0}],
        [{"node": "Send Bale", "type": "main", "index": 0}]
      ]
    },
    "Send Eitaa": {"main": [[{"node": "Save Result", "type": "main", "index": 0}]]},
    "Send Telegram": {"main": [[{"node": "Save Result", "type": "main", "index": 0}]]},
    "Send Bale": {"main": [[{"node": "Save Result", "type": "main", "index": 0}]]}
  }
}
```

### ۳.۲ Lesson Completed Workflow

```json
{
  "name": "Lesson Completed",
  "nodes": [
    {
      "name": "RabbitMQ Trigger",
      "type": "n8n-nodes-base.rabbitmqTrigger",
      "parameters": {
        "queue": "peyda_lesson_completed"
      },
      "position": [250, 300]
    },
    {
      "name": "Check Achievement",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{$json.payload.score}}",
              "operation": "greaterEqual",
              "value2": 100
            }
          ]
        }
      },
      "position": [450, 300]
    },
    {
      "name": "Grant Perfect Score",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{$env.BACKEND_URL}}/webhooks/achievement/",
        "method": "POST",
        "headers": {"X-Webhook-Secret": "={{$env.WEBHOOK_SECRET}}"},
        "body": {
          "user_id": "={{$json.payload.user_id}}",
          "achievement_type": "perfect_score",
          "xp_amount": 50
        }
      },
      "position": [650, 200]
    },
    {
      "name": "Check First Lesson",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{$env.BACKEND_URL}}/api/v1/progress/{{$json.payload.user_id}}/stats/",
        "method": "GET"
      },
      "position": [650, 400]
    },
    {
      "name": "Is First Lesson",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "number": [
            {
              "value1": "={{$json.total_completed_lessons}}",
              "operation": "equal",
              "value2": 1
            }
          ]
        }
      },
      "position": [850, 400]
    },
    {
      "name": "Grant First Lesson",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{$env.BACKEND_URL}}/webhooks/achievement/",
        "method": "POST",
        "headers": {"X-Webhook-Secret": "={{$env.WEBHOOK_SECRET}}"},
        "body": {
          "user_id": "={{$json.payload.user_id}}",
          "achievement_type": "first_lesson",
          "xp_amount": 100
        }
      },
      "position": [1050, 400]
    }
  ]
}
```

---

## ۴. Notification Templates

### ۴.۱ Template Registry

```python
# apps/notifications/templates.py
from typing import Dict, Any

TEMPLATES: Dict[str, Dict[str, Any]] = {
    'welcome': {
        'text': """سلام {name}! 👋

به لِسان خوش آمدی.
برای شروع یادگیری قرآن، وارد برنامه شو.""",
        'channels': ['eitaa', 'telegram', 'bale']
    },
    
    'lesson_reminder': {
        'text': """سلام {name}! 📚

مدتی هست که درس نخوندی.
بیا ادامه بدیم: جزء {juz_number}""",
        'channels': ['eitaa', 'telegram', 'bale']
    },
    
    'achievement_unlocked': {
        'text': """تبریک! 🎉

دستاورد جدید: {achievement_name}
+{xp_amount} XP""",
        'channels': ['eitaa', 'telegram', 'bale']
    },
    
    'juz_completed': {
        'text': """ماشاءالله! 🌟

جزء {juz_number} رو کامل کردی!
+{xp_amount} XP""",
        'channels': ['eitaa', 'telegram', 'bale']
    }
}

def render_template(template_name: str, **kwargs) -> str:
    """Render a notification template"""
    template = TEMPLATES.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")
    
    return template['text'].format(**kwargs)
```

---

## ۵. Monitoring & Analytics

### ۵.۱ Notification Analytics Queries

```sql
-- نرخ موفقیت به تفکیک کانال
SELECT 
    channel,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'sent') as sent,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'sent') / COUNT(*), 2) as success_rate
FROM notifications_notification
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY channel;

-- پرکاربردترین template ها
SELECT 
    template,
    COUNT(*) as total,
    COUNT(DISTINCT user_id) as unique_users
FROM notifications_notification
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY template
ORDER BY total DESC;

-- خطاهای اخیر
SELECT 
    channel,
    template,
    error_message,
    COUNT(*) as count
FROM notifications_notification
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY channel, template, error_message
ORDER BY count DESC
LIMIT 20;
```

### ۵.۲ n8n Execution Monitoring

```python
# management/commands/check_n8n_health.py
import requests
import os
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        n8n_url = os.environ.get('N8N_URL')
        api_key = os.environ.get('N8N_API_KEY')
        
        # Check n8n is running
        try:
            response = requests.get(
                f'{n8n_url}/api/v1/workflows',
                headers={'X-N8N-API-KEY': api_key},
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            self.stderr.write(f'n8n health check failed: {e}')
            return
        
        # Check for failed executions
        executions = requests.get(
            f'{n8n_url}/api/v1/executions',
            headers={'X-N8N-API-KEY': api_key},
            params={'status': 'failed', 'limit': 10}
        ).json()
        
        if executions['data']:
            self.stderr.write(f'Found {len(executions["data"])} failed executions')
            for exec in executions['data']:
                self.stderr.write(f'  - {exec["workflowId"]}: {exec["stoppedAt"]}')
        else:
            self.stdout.write('All workflows healthy')
```

---

## ۶. Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              EVENT FLOW                                  │
└─────────────────────────────────────────────────────────────────────────┘

Backend Service                RabbitMQ              n8n                Backend Webhook
     │                            │                   │                       │
     │  publish(event)            │                   │                       │
     │───────────────────────────>│                   │                       │
     │                            │                   │                       │
     │                            │  consume(queue)   │                       │
     │                            │──────────────────>│                       │
     │                            │                   │                       │
     │                            │                   │  Process workflow     │
     │                            │                   │  (Send notification)  │
     │                            │                   │                       │
     │                            │                   │  POST /webhooks/...   │
     │                            │                   │──────────────────────>│
     │                            │                   │                       │
     │                            │                   │        Save result    │
     │                            │                   │<──────────────────────│
     │                            │                   │                       │
```
