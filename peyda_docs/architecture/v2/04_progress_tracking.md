# معماری لِسان v2 - ردیابی پیشرفت

## ۱. اصل طراحی: اعتبارسنجی سمت کلاینت

### ۱.۱ چرا اعتبارسنجی سمت کلاینت؟

| رویکرد | مزایا | معایب |
|--------|-------|-------|
| **Server-side validation** | امنیت بالا | پیچیدگی، latency، وابستگی به شبکه |
| **Client-side validation** | سادگی، UX بهتر، offline-friendly | قابل دستکاری توسط کاربر |

**تصمیم**: برای MVP، اعتبارسنجی سمت کلاینت انجام می‌شود. دلایل:
- هدف آموزش است نه رقابت
- تقلب ضرری به دیگران نمی‌زند
- سادگی پیاده‌سازی
- UX بهتر (بدون انتظار برای سرور)

### ۱.۲ جریان پاسخ‌دهی

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│  1. دریافت سوالات درس از سرور                                   │
│  2. نمایش سوال به کاربر                                         │
│  3. بررسی پاسخ کاربر (در فرانت‌اند)                              │
│  4. ذخیره نتیجه در state محلی                                   │
│  5. تکرار برای همه سوالات                                       │
│  6. ارسال نتیجه نهایی به سرور (فقط یک‌بار)                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          BACKEND                                 │
├─────────────────────────────────────────────────────────────────┤
│  فقط دریافت می‌کند:                                              │
│  - lesson_id                                                     │
│  - failed_question_ids (سوالات اشتباه)                          │
│  - total_time_ms                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## ۲. API Design

### ۲.۱ دریافت سوالات

```http
GET /api/v1/lessons/{id}/questions/
Authorization: InitData ...
```

**Response:**
```json
{
  "lesson_id": 123,
  "questions": [
    {
      "id": 1,
      "type": "matching",
      "content": {
        "pairs": [
          {"word": "الْحَمْدُ", "translation": "ستایش"},
          {"word": "رَبِّ", "translation": "پروردگار"}
        ]
      },
      "difficulty": 1
    },
    {
      "id": 2,
      "type": "multiple_choice",
      "content": {
        "question": "ترجمه صحیح کدام است؟",
        "ayah_snippet": "رَبِّ الْعَالَمِينَ",
        "correct_answer": "پروردگار جهانیان",
        "wrong_answers": ["پادشاه روز جزا", "خداوند بخشنده", "راه راست"],
        "explanation": "رَبّ = پروردگار، عالَمین = جهانیان"
      },
      "difficulty": 2
    }
  ],
  "total_count": 8
}
```

**نکته مهم**: پاسخ صحیح در محتوای سوال موجود است. فرانت‌اند مسئول اعتبارسنجی است.

### ۲.۲ تکمیل درس

```http
POST /api/v1/lessons/{id}/complete/
Authorization: InitData ...
Content-Type: application/json

{
  "failed_question_ids": [2, 5],
  "total_time_ms": 180000
}
```

**Response:**
```json
{
  "status": "completed",
  "lesson_id": 123,
  "correct_count": 6,
  "wrong_count": 2,
  "score": 75,
  "xp_earned": 15
}
```

---

## ۳. مدل‌های داده

### ۳.۱ LessonProgress (بهبود یافته)

```python
# apps/progress/models.py
class LessonProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'شروع نشده'
        COMPLETED = 'completed', 'تکمیل شده'
        # ❌ حذف شده: IN_PROGRESS (چون هر چیزی سمت کلاینت است)
    
    user_id = models.PositiveIntegerField(db_index=True)
    lesson_id = models.PositiveIntegerField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    correct_count = models.PositiveSmallIntegerField(default=0)
    wrong_count = models.PositiveSmallIntegerField(default=0)
    total_time_ms = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user_id', 'lesson_id']
        indexes = [
            models.Index(fields=['user_id', 'status']),
        ]
```

### ۳.۲ FailedQuestion (جدید)

```python
class FailedQuestion(models.Model):
    """سوالاتی که کاربر اشتباه پاسخ داده
    
    برای:
    - تحلیل سوالات مشکل‌دار
    - پیشنهاد مرور شخصی‌سازی شده
    """
    user_id = models.PositiveIntegerField(db_index=True)
    question_id = models.PositiveIntegerField(db_index=True)
    lesson_id = models.PositiveIntegerField(db_index=True)
    failed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'question_id']),
            models.Index(fields=['question_id']),  # برای تحلیل سوالات
        ]
```

---

## ۴. ProgressService (بهبود یافته)

```python
# services/progress_service.py
from typing import List
from apps.progress.models import UserProgress, LessonProgress, FailedQuestion
from apps.courses.models import Lesson, LessonQuestion

class ProgressService(BaseService):
    
    def complete_lesson(
        self,
        user_id: int,
        lesson_id: int,
        failed_question_ids: List[int],
        total_time_ms: int
    ) -> dict:
        """تکمیل درس"""
        
        # 1. Get lesson info
        lesson = Lesson.objects.select_related('stage__juz').get(id=lesson_id)
        total_questions = LessonQuestion.objects.filter(lesson_id=lesson_id).count()
        
        # 2. Calculate counts
        wrong_count = len(failed_question_ids)
        correct_count = total_questions - wrong_count
        
        # 3. Validate sanity
        if wrong_count > total_questions:
            raise ValueError("تعداد پاسخ‌های اشتباه بیشتر از تعداد سوالات است")
        
        # 4. Create/Update progress
        progress, created = LessonProgress.objects.update_or_create(
            user_id=user_id,
            lesson_id=lesson_id,
            defaults={
                'status': 'completed',
                'correct_count': correct_count,
                'wrong_count': wrong_count,
                'total_time_ms': total_time_ms,
                'completed_at': self._clock.now()
            }
        )
        
        # 5. Record failed questions (for analytics & review)
        if failed_question_ids:
            FailedQuestion.objects.bulk_create([
                FailedQuestion(
                    user_id=user_id,
                    question_id=qid,
                    lesson_id=lesson_id
                )
                for qid in failed_question_ids
            ], ignore_conflicts=True)
        
        # 6. Update user progress pointer
        self._update_user_progress(user_id, lesson)
        
        # 7. Calculate score & XP
        score = self._calculate_score(correct_count, total_questions)
        xp = self._calculate_xp(score, lesson.stage.juz.number)
        
        # 8. Publish event
        self._event_bus.publish('lesson.completed', {
            'user_id': user_id,
            'lesson_id': lesson_id,
            'juz_id': lesson.stage.juz.id,
            'stage_id': lesson.stage.id,
            'score': score,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'failed_question_ids': failed_question_ids,
            'total_time_ms': total_time_ms,
            'timestamp': self._clock.now().isoformat()
        })
        
        return {
            'status': 'completed',
            'lesson_id': lesson_id,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'score': score,
            'xp_earned': xp
        }
    
    def _calculate_score(self, correct: int, total: int) -> int:
        """محاسبه امتیاز ۰-۱۰۰"""
        if total == 0:
            return 0
        return int((correct / total) * 100)
    
    def _calculate_xp(self, score: int, juz_number: int) -> int:
        """محاسبه XP بر اساس امتیاز و جزء"""
        base_xp = 10
        score_multiplier = score / 100
        juz_bonus = juz_number  # جزء‌های بالاتر XP بیشتر
        return int(base_xp * score_multiplier * (1 + juz_bonus * 0.1))
    
    def _update_user_progress(self, user_id: int, lesson: Lesson):
        """به‌روزرسانی موقعیت فعلی کاربر"""
        UserProgress.objects.update_or_create(
            user_id=user_id,
            defaults={
                'current_juz_id': lesson.stage.juz.id,
                'current_stage_id': lesson.stage.id,
                'current_lesson_id': lesson.id
            }
        )
    
    def get_failed_questions_for_review(self, user_id: int, limit: int = 20) -> List[int]:
        """سوالات پرتکرار اشتباه برای مرور"""
        from django.db.models import Count
        
        return list(
            FailedQuestion.objects
            .filter(user_id=user_id)
            .values('question_id')
            .annotate(fail_count=Count('id'))
            .order_by('-fail_count')
            .values_list('question_id', flat=True)[:limit]
        )
```

---

## ۵. تحلیل سوالات

### ۵.۱ Query برای سوالات مشکل‌دار

```python
# management/commands/analyze_questions.py
from django.db.models import Count, F

def get_problematic_questions(min_failures: int = 10, max_success_rate: float = 0.5):
    """سوالاتی که کاربران زیادی در آن‌ها اشتباه می‌کنند"""
    
    from apps.progress.models import FailedQuestion, LessonProgress
    
    # Count failures per question
    failures = (
        FailedQuestion.objects
        .values('question_id')
        .annotate(fail_count=Count('id'))
        .filter(fail_count__gte=min_failures)
    )
    
    # Compare with total attempts (lessons completed containing this question)
    # This requires joining with LessonQuestion
    
    return failures
```

### ۵.۲ Dashboard Query

```sql
-- سوالاتی با بیشترین خطا
SELECT 
    q.id,
    q.question_type,
    q.juz_number,
    COUNT(fq.id) as fail_count,
    q.feedback_score
FROM questions_question q
JOIN progress_failedquestion fq ON q.id = fq.question_id
GROUP BY q.id
ORDER BY fail_count DESC
LIMIT 20;
```

---

## ۶. ملاحظات

### ۶.۱ چه چیزهایی ذخیره نمی‌شوند

| داده | دلیل عدم ذخیره |
|------|----------------|
| پاسخ دقیق کاربر | حجم بالا، کم‌کاربرد |
| زمان هر سوال | پیچیدگی، حریم خصوصی |
| تعداد تلاش‌ها | Gamification منفی |

### ۶.۲ چه چیزهایی ذخیره می‌شوند

| داده | دلیل ذخیره |
|------|------------|
| شناسه سوالات اشتباه | تحلیل کیفیت، مرور شخصی |
| امتیاز کل درس | پیشرفت، انگیزه |
| زمان کل درس | تحلیل رفتار |

### ۶.۳ Anti-Cheat (V2)

اگر در آینده نیاز به جلوگیری از تقلب باشد:
- Hash پاسخ‌ها و ارسال به سرور
- Server-side validation برای مسابقات
- Rate limiting برای درس‌های تکراری
