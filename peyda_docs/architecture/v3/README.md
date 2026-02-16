# معماری لِسان v3

> بازنگری نهایی بر اساس تمام HUMAN OVERRIDE ها

## تغییرات اصلی نسبت به v2

| موضوع | v2 | v3 |
|-------|----|----|
| **Token Format** | جداگانه headers | `PEYDA:eitaa\|init_data` یکجا |
| **Middleware** | Auth Middleware | `authentication.py` (DRF) |
| **Session** | ❌ نداشت | ✅ Session model با start_param |
| **DateTime** | ISO 8601 | **Unix timestamp** |
| **Idempotency** | ❌ نداشت | ✅ `idempotency_key` در write requests |
| **CQRS** | پیشنهاد | ✅ پیاده‌سازی شده |
| **Webhook Access** | مستقیم به Model | ❌ فقط از طریق Command |
| **Signals** | در Domain | ✅ Interface Layer |
| **Bot State** | ❌ نداشت | ✅ Redis State Management |
| **n8n Workflows** | فقط توضیح | ✅ JSON + Import/Export |
| **Notifications** | ❌ نداشت | ✅ Logging Model |

---

## فهرست مستندات

| فایل | موضوع |
|------|-------|
| [01_authentication.md](./01_authentication.md) | Token format، Session model، AuthService |
| [02_api_contracts.md](./02_api_contracts.md) | Unix timestamps، Idempotency، Pydantic contracts |
| [03_interface_layers.md](./03_interface_layers.md) | REST API، n8n Handlers، Bot Webhook، Signals |
| [04_n8n_workflows.md](./04_n8n_workflows.md) | Workflow storage، Import/Export، Notification logging |
| [05_cqrs.md](./05_cqrs.md) | Commands، Queries، Dependency Injection |

---

## خلاصه HUMAN OVERRIDE ها

### ۱. احراز هویت
```
قبل: Middleware جداگانه + هدرهای جداگانه
بعد: DRF Authentication class
      Token: "InitData PEYDA:eitaa|<init_data>"
      + Session model با start_param
```

### ۲. DateTime
```python
# قبل
{"completed_at": "2024-01-15T14:30:00Z"}

# بعد - همه جا Unix timestamp
{"completed_at": 1705329000}
```

### ۳. Idempotency
```python
# Write requests باید idempotency_key داشته باشند
class CompleteLessonRequest(WriteRequest):
    idempotency_key: UUID  # اجباری
    failed_question_ids: List[int]
    total_time_ms: int
```

### ۴. Interface Layer - بدون دسترسی مستقیم به Model
```python
# ❌ نادرست - در Webhook
UserAchievement.objects.create(...)

# ✅ درست - از طریق Command
command = self.get_command(GrantAchievementCommand)
command.execute(user_id=user_id, ...)
```

### ۵. CQRS
```
services/
├── commands/              # Write operations
│   ├── complete_lesson.py
│   └── grant_achievement.py
└── queries/               # Read operations
    ├── get_lesson_questions.py
    └── get_user_progress.py
```

### ۶. Signals در Interface Layer
```python
# apps/signals/handlers/cache_invalidation.py
@receiver([post_save, post_delete], sender=Syllabus)
def invalidate_syllabus_cache(sender, instance, **kwargs):
    command = container.get(InvalidateCacheCommand)
    command.execute(cache_key=f"juz:{instance.juz_id}:syllabus")
```

### ۷. n8n Workflow Storage
```
infrastructure/n8n/
├── workflows/           # JSON files (version controlled)
│   ├── user_welcome.json
│   └── lesson_completed.json
├── export.py           # Export from n8n GUI
└── import.py           # Import on deploy
```

### ۸. Notification Logging
```python
# n8n ارسال می‌کند → webhook نتیجه را ثبت می‌کند
POST /webhooks/notification-result/
{
    "notification_id": "...",
    "user_id": 123,
    "channel": "eitaa",
    "template": "welcome",
    "status": "sent",
    "sent_at": 1705329000
}
```

### ۹. Bot Webhook با State Management
```python
# Redis-based state for bot conversations
class RedisBotState(BotState):
    def get(self, user_id: str, platform: str) -> dict
    def set(self, user_id: str, platform: str, state: dict, ttl: int)
    def delete(self, user_id: str, platform: str)
```

---

## دیاگرام معماری

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTERFACE LAYER                                    │
├───────────────┬───────────────┬───────────────┬───────────────┬─────────────┤
│   REST API    │ n8n Handlers  │ Bot Webhook   │   Signals     │   Admin     │
│  (ViewSets)   │  (Internal)   │  (External)   │   (Django)    │  (Django)   │
└───────┬───────┴───────┬───────┴───────┬───────┴───────┬───────┴──────┬──────┘
        │               │               │               │              │
        └───────────────┴───────────────┴───────────────┴──────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │      APPLICATION LAYER         │
                        ├───────────────┬───────────────┤
                        │   Commands    │   Queries     │
                        └───────┬───────┴───────┬───────┘
                                │               │
                        ┌───────┴───────────────┴───────┐
                        │        DOMAIN LAYER           │
                        │    (Models, Business Logic)    │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │     INFRASTRUCTURE LAYER       │
                        ├───────┬───────┬───────┬───────┤
                        │EventBus│ Cache │ Clock │  DB   │
                        └───────┴───────┴───────┴───────┘
```

---

## Interface ها

| Interface | Authentication | State | Model Access |
|-----------|---------------|-------|--------------|
| REST API | InitData Token | Stateless | ❌ Command/Query |
| n8n Handlers | Webhook Secret | Stateless | ❌ Command |
| Bot Webhook | Platform Signature | Redis | ❌ Command |
| Signals | N/A (internal) | N/A | ❌ Command |
| Admin | Django Session | Django | ✅ Direct (OK) |

---

## قواعد مهم

### ۱. DateTime
- **همه** datetime ها بین frontend/backend/n8n به صورت **Unix timestamp (ثانیه)** هستند
- در DB می‌تواند DateTimeField باشد، موقع serialize به timestamp تبدیل می‌شود

### ۲. Idempotency
- **همه** write requests باید `idempotency_key` داشته باشند
- Backend نتیجه را cache می‌کند و برای درخواست تکراری همان نتیجه را برمی‌گرداند

### ۳. No Direct Model Access in Interface
- Interface ها (ViewSet، Webhook، Signal) **هرگز** مستقیم به Model دسترسی ندارند
- فقط از طریق Command (write) یا Query (read)

### ۴. Event Payloads
- همه event ها `timestamp` دارند (Unix timestamp)
- User-related events شامل `user_id` هستند

---

## تصمیمات قبول شده

| تصمیم | وضعیت | توضیح |
|-------|-------|-------|
| Repository Pattern | ❌ رد شد | ریسک coupling با ORM قبول شد |
| Backup Strategy | ❌ رد شد | K8s مدیریت می‌کند |
| CQRS | ✅ قبول | جدا کردن Commands و Queries |
| Health Check | ✅ قبول | پیاده‌سازی شود |
| Structured Logging | ✅ قبول | JSON logging |
| Webhook Secret | ✅ قبول | X-Webhook-Secret header |

---

## Checklist پیاده‌سازی

### فوری (Sprint 1)
- [ ] Session model و migration
- [ ] InitData authentication class
- [ ] Idempotency decorator و model
- [ ] Base Command و Query classes
- [ ] Webhook secret verification

### کوتاه‌مدت (Sprint 2)
- [ ] CompleteLessonCommand
- [ ] GetLessonQuestionsQuery
- [ ] Notification model و SaveNotificationResultCommand
- [ ] n8n workflow export/import scripts
- [ ] Health check endpoint

### میان‌مدت (Sprint 3-4)
- [ ] Bot webhook با state management
- [ ] Signal handlers در interface layer
- [ ] Structured JSON logging
- [ ] Integration tests
