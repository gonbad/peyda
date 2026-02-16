# معماری لِسان v2

> بازنگری معماری بر اساس HUMAN OVERRIDE notes

## تغییرات نسبت به v1

| موضوع | v1 | v2 |
|-------|----|----|
| **احراز هویت** | توکن ساده | InitData از Web App SDK با hash verification |
| **API Views** | APIView | ViewSet + Pydantic contracts |
| **Validation** | در View | Pydantic BaseModel ها |
| **Event Bus** | publish + subscribe | فقط publish (n8n مصرف‌کننده) |
| **Progress** | Server-side validation | Client-side validation، فقط نتیجه نهایی |
| **Answer tracking** | ذخیره هر پاسخ | فقط failed_question_ids |

---

## فهرست مستندات

| فایل | موضوع |
|------|-------|
| [01_authentication.md](./01_authentication.md) | احراز هویت با InitData، hash verification، middleware |
| [02_api_contracts.md](./02_api_contracts.md) | ViewSet، Pydantic models، request/response contracts |
| [03_n8n_integration.md](./03_n8n_integration.md) | Event Bus، RabbitMQ، n8n workflows، webhooks |
| [04_progress_tracking.md](./04_progress_tracking.md) | Client-side validation، FailedQuestion model |
| [05_risks_improvements.md](./05_risks_improvements.md) | ریسک‌ها، باگ‌های احتمالی، پیشنهادات |

---

## خلاصه HUMAN OVERRIDE ها

### ۱. احراز هویت
```
قبل: Authorization: MessengerToken <signed_token>
بعد: Authorization: InitData <initData>
     + X-Platform: eitaa|telegram|bale
     + X-App-SKU: PEYDA
     + IP از X-Forwarded-For
     + Verify hash با bot_token
```

### ۲. ViewSet + Pydantic
```python
# قبل
class JuzDetailView(APIView):
    def get(self, request, pk):
        ...

# بعد
class JuzViewSet(BaseViewSet):
    def retrieve(self, request, pk=None):
        return self.success_response(data, JuzDetailResponse)

class CompleteLessonRequest(BaseModel):
    lesson_id: int
    failed_question_ids: List[int]
    total_time_ms: int
```

### ۳. Event Bus (فقط Publish)
```python
# قبل
class EventBus(ABC):
    def publish(self, ...): pass
    def subscribe(self, ...): pass  # ❌ حذف شد

# بعد
class EventBus(ABC):
    def publish(self, ...): pass
    # n8n از RabbitMQ می‌خواند و webhook می‌زند
```

### ۴. Progress Tracking
```python
# قبل: ذخیره هر پاسخ جداگانه
POST /api/v1/answers/
{question_id, answer, is_correct, ...}

# بعد: فقط نتیجه نهایی درس
POST /api/v1/lessons/{id}/complete/
{failed_question_ids: [2, 5], total_time_ms: 180000}
```

---

## ریسک‌های شناسایی شده

| ریسک | شدت | وضعیت |
|------|-----|-------|
| Rate Limiting نیست | 🟡 | ⚠️ نیاز به پیاده‌سازی |
| Webhook Security | 🔴 | ⚠️ نیاز به internal-only |
| Race Condition در Progress | 🟡 | ⚠️ نیاز به select_for_update |
| Cache Invalidation | 🟡 | ⚠️ نیاز به signals |
| RabbitMQ Connection | 🟡 | ⚠️ نیاز به retry logic |

---

## باگ‌های احتمالی

1. **Race Condition**: اگر کاربر دو بار سریع درس را complete کند
2. **N+1 Query**: در دریافت سوالات درس
3. **Cache Stale**: بعد از تغییر در admin
4. **Connection Lost**: در publish به RabbitMQ

---

## اقدامات فوری (قبل از Production)

```bash
# 1. Rate Limiting
pip install django-ratelimit

# 2. Health Check
GET /api/v1/health/

# 3. Webhook Security
ALLOWED_WEBHOOK_IPS=['10.0.0.0/8', ...]

# 4. Structured Logging
pip install python-json-logger
```

---

## دیاگرام جریان

```
┌──────────┐  InitData   ┌──────────┐  Service   ┌──────────┐
│ Mini-App │────────────>│  ViewSet │───────────>│  Domain  │
│ (React)  │<────────────│ +Pydantic│<───────────│  Models  │
└──────────┘  Response   └──────────┘            └──────────┘
                              │
                              │ publish()
                              ▼
                         ┌──────────┐  consume   ┌──────────┐
                         │ RabbitMQ │───────────>│   n8n    │
                         └──────────┘            └────┬─────┘
                                                      │
                                                      │ webhook
                                                      ▼
                                                 ┌──────────┐
                                                 │ Internal │
                                                 │ Webhooks │
                                                 └──────────┘
```
