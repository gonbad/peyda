# معماری پروژه لِسان - بخش ۱: مرور کلی

## ۱. خلاصه پروژه

**لِسان** یک Mini-App یادگیری زبان قرآن است (الهام از Duolingo) که از طریق پیام‌رسان‌های ایتا، تلگرام و بله قابل دسترسی است.

### ویژگی‌های اصلی MVP:
- **درسنامه (Syllabus)**: آیات با ترجمه، صوت و تحلیل واژگانی
- **درس‌ها (Lessons)**: سوالات تمرینی (۷-۱۰ سوال در هر درس)
- **ثبت پاسخ‌ها**: ذخیره پاسخ‌های کاربر برای تحلیل

---

## ۲. پشته فناوری (Tech Stack)

| لایه | فناوری |
|------|--------|
| **Backend** | Django 5.x + Django REST Framework |
| **Database** | PostgreSQL |
| **Cache** | Redis (V2) |
| **Message Queue** | RabbitMQ (Event Bus) |
| **Workflow** | n8n |
| **Container** | Docker Compose |
| **Frontend** | React (JavaScript) |

---

## ۳. معماری لایه‌ای (DDD-Inspired)

```
┌─────────────────────────────────────────────────────────────────┐
│                     5. FRONTEND LAYER                           │
│                    (React Mini-App)                             │
├─────────────────────────────────────────────────────────────────┤
│                     4. INTERFACE LAYER                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │  REST API    │  n8n Hooks   │ Django Admin │  Management  │ │
│  │  (views.py)  │  (webhooks)  │  (signals)   │  Commands    │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                  3. APPLICATION LAYER                           │
│              (Services / Commands / Queries)                    │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │   Quran      │   Lesson     │   Question   │   Progress   │ │
│  │   Service    │   Service    │   Service    │   Service    │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    2. DOMAIN LAYER                              │
│                   (Django Apps/Models)                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │    quran     │   courses    │  questions   │   users      │ │
│  │              │              │              │   progress   │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                 1. INFRASTRUCTURE LAYER                         │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │  Event Bus   │    Cache     │    Clock     │   Storage    │ │
│  │  (RabbitMQ)  │   (Redis)    │  (datetime)  │    (S3)      │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## ۴. توضیح لایه‌ها

### ۴.۱ Infrastructure Layer (زیرساخت)
مسئولیت: ارتباط با سیستم‌های خارجی

```python
backend/infrastructure/
├── event_bus/
│   ├── __init__.py
│   ├── interface.py      # Abstract interface
│   ├── rabbitmq.py       # RabbitMQ implementation
│   └── fake.py           # Fake for testing
├── cache/
│   ├── __init__.py
│   ├── interface.py
│   ├── redis.py
│   └── fake.py
├── clock/
│   ├── __init__.py
│   ├── interface.py
│   └── fake.py           # For testing with fixed time
└── bootstrap.py          # Dependency Injection container
```

**قانون**: این لایه هیچ وابستگی به لایه‌های بالاتر ندارد.

### ۴.۲ Domain Layer (دامنه)
مسئولیت: مدل‌های داده و قوانین دامنه

```python
backend/apps/
├── quran/           # Surah, Ayah, Word, WordPart
├── courses/         # Course, Level, Juz, Stage, Lesson, Syllabus
├── questions/       # Question, QuestionFeedback, QuestionReport
├── users/           # User
└── progress/        # UserProgress, LessonProgress, UserAnswer
```

**قانون**: FK فقط درون همان app مجاز است. برای ارتباط بین app ها از ID استفاده می‌شود.

### ۴.۳ Application Layer (کاربرد)
مسئولیت: منطق کسب‌وکار، هماهنگی بین Domain ها

```python
backend/services/
├── quran_service.py      # خواندن آیات، کلمات
├── lesson_service.py     # مدیریت درس‌ها و درسنامه
├── question_service.py   # دریافت سوالات درس
├── progress_service.py   # ثبت پاسخ، محاسبه پیشرفت
└── auth_service.py       # احراز هویت از پیام‌رسان
```

**قانون**: 
- Services می‌توانند از Infrastructure (از طریق DI) و Domain استفاده کنند
- Services نباید مستقیماً HTTP request/response ببینند

### ۴.۴ Interface Layer (واسط)
مسئولیت: دریافت درخواست، ارسال پاسخ - بدون منطق

**۴ نقطه ورود:**

| نقطه ورود | توضیح | فایل |
|-----------|-------|------|
| **REST API** | درخواست‌های فرانت‌اند | `views.py`, `urls.py` |
| **n8n Webhooks** | فراخوانی از workflow | `webhooks.py` |
| **Django Admin** | رویدادهای ادمین | `signals.py` |
| **Management Commands** | اسکریپت‌های CLI | `management/commands/` |

---

## ۵. احراز هویت

### کاربران عادی (از پیام‌رسان)
```
Request Header:
Authorization: MessengerToken <signed_token> **HUMAN OVERRIDE**: this is init data from web app sdk. we check hash based on inti data and bot token in that platform

Token contains:
- platform: eitaa | telegram | bale
- platform_user_id: string
- username: string (optional)
- display_name: string (optional)
```

### کاربران ادمین
- سیستم پیش‌فرض Django Admin
- Session-based authentication

---

## ۶. ساختار پروژه

```
peyda/
├── backend/
│   ├── apps/                    # Domain Layer
│   │   ├── quran/
│   │   ├── courses/
│   │   ├── questions/
│   │   ├── users/
│   │   └── progress/
│   ├── services/                # Application Layer
│   ├── infrastructure/          # Infrastructure Layer
│   ├── config/                  # Django settings
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── manage.py
│   └── requirements.txt
├── frontend/                    # React Mini-App
├── config/
│   └── develop/
│       └── docker-compose.yaml
├── resources/                   # Data files (xlsx, csv, db)
├── scripts/                     # Data processing scripts
└── peyda_docs/                  # Documentation
```

---

## ۷. اصول طراحی

1. **جداسازی لایه‌ها**: هر لایه فقط به لایه پایین‌تر وابسته است
2. **Dependency Injection**: Infrastructure از طریق DI تزریق می‌شود
3. **No Cross-App FK**: بین app های مختلف از ID استفاده می‌شود
4. **JSON for Flexibility**: محتوای سوالات و درسنامه در JSONB ذخیره می‌شود
5. **Event-Driven**: رویدادها از طریق Event Bus منتشر می‌شوند
6. **Order Spacing**: فیلدهای ترتیب با فاصله ۱۰۰۰۰ برای درج آسان
