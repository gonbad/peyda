# معماری پروژه لِسان

## فهرست مستندات

| فایل | موضوع |
|------|-------|
| [01_overview.md](./01_overview.md) | مرور کلی، لایه‌ها، ساختار پروژه |
| [02_domain_models.md](./02_domain_models.md) | مدل‌های دامنه (Quran, Courses, Questions, Users, Progress) |
| [03_services_apis.md](./03_services_apis.md) | سرویس‌ها و API Endpoints |
| [04_infrastructure.md](./04_infrastructure.md) | زیرساخت، تست‌نویسی، Docker |

---

## خلاصه معماری

### پشته فناوری
```
Django 5.x + DRF | PostgreSQL | RabbitMQ | Redis | Docker Compose
```

### لایه‌ها (پایین به بالا)
```
1. Infrastructure   → EventBus, Cache, Clock (با Fake برای تست)
2. Domain          → Django Apps (quran, courses, questions, users, progress)
3. Application     → Services (منطق کسب‌وکار)
4. Interface       → REST API, n8n Webhooks, Admin, Management Commands
5. Frontend        → React Mini-App
```

### اصول کلیدی
- **DDD-Inspired**: جداسازی Domain ها
- **No Cross-App FK**: استفاده از ID به جای Foreign Key بین app ها
- **Dependency Injection**: Infrastructure از طریق Container تزریق می‌شود
- **No Mocking**: استفاده از Fake implementations در تست
- **JSON Flexibility**: محتوای سوالات و درسنامه در JSONB
- **Order Spacing**: فیلدهای ترتیب با فاصله ۱۰۰۰۰

---

## نقشه Domain ها

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   QURAN     │    │   COURSES   │    │  QUESTIONS  │
│  ─────────  │    │  ─────────  │    │  ─────────  │
│  Surah      │    │  Course     │    │  Question   │
│  Ayah       │    │  Level      │    │  Feedback   │
│  Word       │    │  Juz        │    │  Report     │
│  WordPart   │    │  Stage      │    └─────────────┘
└─────────────┘    │  Lesson     │
                   │  Syllabus   │    ┌─────────────┐
                   │  LessonQues.│    │   USERS     │
                   └─────────────┘    │  ─────────  │
                                      │  User       │
┌─────────────┐                       └─────────────┘
│  PROGRESS   │
│  ─────────  │
│  UserProg.  │
│  LessonProg.│
│  UserAnswer │
└─────────────┘
```

---

## API Summary

| Method | Endpoint | توضیح |
|--------|----------|-------|
| GET | `/api/v1/courses/` | لیست دوره‌ها |
| GET | `/api/v1/juz/{id}/syllabus/` | درسنامه جزء |
| GET | `/api/v1/lessons/{id}/questions/` | سوالات درس |
| GET | `/api/v1/me/progress/` | پیشرفت کاربر |
| POST | `/api/v1/answers/` | ثبت پاسخ |
| POST | `/api/v1/lessons/{id}/complete/` | تکمیل درس |

---

## Event Types

| Event | Trigger |
|-------|---------|
| `user.created` | ثبت‌نام کاربر جدید |
| `answer.submitted` | ثبت پاسخ |
| `lesson.completed` | تکمیل درس |
| `question.feedback` | بازخورد سوال |

---

## Quick Start

```bash
# Start services
cd config/develop
docker compose up -d

# Import data
docker compose exec api python manage.py import_quran_excel
docker compose exec api python manage.py generate_syllabi
docker compose exec api python manage.py package_questions

# Run tests
docker compose exec api pytest
```
