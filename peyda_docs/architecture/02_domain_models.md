# معماری پروژه لِسان - بخش ۲: مدل‌های دامنه

## ۱. نمای کلی Domain ها

```
┌─────────────────────────────────────────────────────────────────┐
│                         DOMAINS                                  │
├─────────────────┬─────────────────┬─────────────────────────────┤
│                 │                 │                             │
│     QURAN       │    COURSES      │    QUESTIONS                │
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐             │
│  │  Surah    │  │  │  Course   │  │  │ Question  │             │
│  │  Ayah     │  │  │  Level    │  │  │ Feedback  │             │
│  │  Word     │  │  │  Juz      │  │  │ Report    │             │
│  │  WordPart │  │  │  Stage    │  │  └───────────┘             │
│  └───────────┘  │  │  Lesson   │  │                             │
│                 │  │  Syllabus │  │    USERS                    │
│                 │  │LessonQues.│  │  ┌───────────┐             │
│                 │  └───────────┘  │  │   User    │             │
│                 │                 │  └───────────┘             │
│                 │                 │                             │
│                 │                 │    PROGRESS                 │
│                 │                 │  ┌───────────┐             │
│                 │                 │  │UserProgress│             │
│                 │                 │  │LessonProg. │             │
│                 │                 │  │UserAnswer  │             │
│                 │                 │  └───────────┘             │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

---

## ۲. Domain: Quran (قرآن)

### ۲.۱ Surah (سوره)
```python
class Surah(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)  # 1-114
    name_arabic = models.CharField(max_length=50)           # الفاتحة
    name_persian = models.CharField(max_length=50)          # فاتحه
    ayah_count = models.PositiveSmallIntegerField()
    revelation_type = models.CharField(choices=['meccan', 'medinan'])
```

### ۲.۲ Ayah (آیه)
```python
class Ayah(models.Model):
    surah = models.ForeignKey(Surah, on_delete=CASCADE)
    number = models.PositiveSmallIntegerField()             # 1-286
    global_number = models.PositiveSmallIntegerField()      # 1-6236
    text_arabic = models.TextField()
    text_arabic_simple = models.TextField()                 # بدون اعراب
    translation_maleki = models.TextField()
    juz_number = models.PositiveSmallIntegerField()         # 1-30
    hizb_number = models.PositiveSmallIntegerField()        # 1-120
    
    # Famous verse markers
    is_famous = models.BooleanField(default=False)
    famous_phrase = models.CharField(null=True)             # بخش معروف
    famous_tags = models.CharField(null=True)               # توحید,دعا
    
    class Meta:
        unique_together = ['surah', 'number']
        indexes = [
            Index(fields=['juz_number']),
            Index(fields=['global_number']),
        ]
```

### ۲.۳ Word (کلمه)
```python
class Word(models.Model):
    ayah = models.ForeignKey(Ayah, on_delete=CASCADE)
    position = models.PositiveSmallIntegerField()
    text_arabic = models.CharField(max_length=100)
    text_arabic_simple = models.CharField(max_length=100)
    translation_persian = models.CharField(max_length=200)
    root = models.CharField(max_length=10, null=True)       # ح-م-د
    lemma = models.CharField(max_length=50, null=True)
    frequency_count = models.PositiveIntegerField(default=0)
    
    # For syllabus highlighting
    is_in_famous_ayah = models.BooleanField(default=False)
    is_in_famous_phrase = models.BooleanField(default=False)
    score = models.PositiveSmallIntegerField(default=0)     # priority score
    
    class Meta:
        unique_together = ['ayah', 'position']
```

### ۲.۴ WordPart (بخش کلمه - تحلیل مورفولوژی)
```python
class WordPart(models.Model):
    word = models.ForeignKey(Word, on_delete=CASCADE)
    position = models.PositiveSmallIntegerField()
    form = models.CharField(max_length=50)                  # شکل ظاهری
    tag = models.CharField(max_length=10)                   # N/V/ADJ/P/...
    
    # Morphological features
    root = models.CharField(max_length=10, null=True)
    lemma = models.CharField(max_length=50, null=True)
    gender = models.CharField(max_length=1, null=True)      # M/F
    number = models.CharField(max_length=1, null=True)      # S/D/P
    case = models.CharField(max_length=3, null=True)        # NOM/ACC/GEN
    tense = models.CharField(max_length=4, null=True)       # PERF/IMPF/IMPV
    person = models.CharField(max_length=1, null=True)      # 1/2/3
```

---

## ۳. Domain: Courses (دوره‌ها)

### ۳.۱ Course (دوره)
```python
class Course(models.Model):
    name = models.CharField(max_length=100)                 # زبان قرآن
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
```

### ۳.۲ Level (سطح)
```python
class Level(models.Model):
    course = models.ForeignKey(Course, on_delete=CASCADE)
    number = models.PositiveSmallIntegerField()             # 1-7
    order = models.PositiveIntegerField()                   # با فاصله 10000
    name = models.CharField(max_length=100)                 # سطح ۱
    focus = models.CharField(max_length=50, blank=True)     # حفظ
    is_active = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['course', 'order']
        unique_together = ['course', 'number']
```

### ۳.۳ Juz (جزء)
```python
class Juz(models.Model):
    level = models.ForeignKey(Level, on_delete=CASCADE)
    number = models.PositiveSmallIntegerField()             # 1-30
    start_ayah_global_id = models.PositiveIntegerField()
    end_ayah_global_id = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['level', 'number']
        unique_together = ['level', 'number']
```

### ۳.۴ Stage (مرحله)
```python
class Stage(models.Model):
    class StageType(models.TextChoices):
        NORMAL = 'normal', 'عادی'           # حزب 1-4
        REVIEW = 'review', 'مرور'           # سوالات قبلی
        TREASURE = 'treasure', 'صندوقچه'    # مرحله خاص
        SKIP = 'skip', 'پرش'                # برای پرش به جزء بعد
    
    juz = models.ForeignKey(Juz, on_delete=CASCADE)
    hizb_number = models.PositiveSmallIntegerField(null=True)  # 1-4
    stage_type = models.CharField(choices=StageType.choices)
    order = models.PositiveIntegerField()                   # با فاصله 10000
    is_visible = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['juz', 'order']
```

### ۳.۵ Lesson (درس)
```python
class Lesson(models.Model):
    stage = models.ForeignKey(Stage, on_delete=CASCADE)
    order = models.PositiveIntegerField()                   # با فاصله 10000
    is_review = models.BooleanField(default=False)          # درس مروری
    
    class Meta:
        ordering = ['stage', 'order']
```

### ۳.۶ LessonQuestion (سوال درس)
```python
class LessonQuestion(models.Model):
    """ارتباط چند به چند درس و سوال
    question_id به جای FK (چون Question در app دیگر است)
    """
    lesson = models.ForeignKey(Lesson, on_delete=CASCADE)
    question_id = models.PositiveIntegerField(db_index=True)
    order = models.PositiveIntegerField()                   # با فاصله 10000
    
    class Meta:
        unique_together = ['lesson', 'question_id']
```

### ۳.۷ Syllabus (درسنامه)
```python
class Syllabus(models.Model):
    """درسنامه با محتوای بلوکی (Block-based Content)"""
    
    class SyllabusType(models.TextChoices):
        QURAN_TEXT = 'quran_text', 'متن قرآن'
        DIALOGUE = 'dialogue', 'گفتگو'
        GRAMMAR = 'grammar', 'گرامر'
    
    juz = models.ForeignKey(Juz, on_delete=CASCADE)
    syllabus_type = models.CharField(choices=SyllabusType.choices)
    order = models.PositiveIntegerField(default=10000)
    content = models.JSONField()                            # Block-based JSON
```

**ساختار JSON محتوای درسنامه:**
```json
{
  "juz_number": 1,
  "sections": [
    {
      "surah_number": 1,
      "surah_name": "الفاتحة",
      "surah_name_persian": "فاتحه",
      "ayahs": [
        {
          "number": 0,
          "text_arabic": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
          "translation": "به نام خداوند بخشنده مهربان",
          "words": [
            {"text": "بِسْمِ", "translation": "به نام"},
            {"text": "اللَّهِ", "translation": "خدا"}
          ],
          "audio_url": "/audio/ayah/001001.mp3"
        }
      ]
    }
  ]
}
```

---

## ۴. Domain: Questions (سوالات)

### ۴.۱ Question (سوال)
```python
class Question(models.Model):
    class QuestionType(models.TextChoices):
        MATCHING = 'matching', 'جفت‌سازی'
        FILL_BLANK = 'fill_blank', 'جای خالی'
        SENTENCE_BUILDING = 'sentence_building', 'جمله‌سازی'
        MULTIPLE_CHOICE = 'multiple_choice', 'چند گزینه‌ای'
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'پیش‌نویس'
        UNDER_REVIEW = 'under_review', 'در حال بررسی'
        PUBLISHED = 'published', 'منتشر شده'
    
    question_type = models.CharField(choices=QuestionType.choices)
    content = models.JSONField()                            # ساختار متفاوت
    juz_number = models.PositiveSmallIntegerField(null=True)
    hizb_number = models.PositiveSmallIntegerField(null=True)  # 1-4
    difficulty = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(choices=Status.choices)
    feedback_score = models.IntegerField(default=0)         # 👍 - 👎
    is_active = models.BooleanField(default=True)
```

**ساختار JSON برای انواع سوالات:**

```json
// matching
{
  "pairs": [
    {"word": "الْحَمْدُ", "translation": "ستایش"},
    {"word": "رَبِّ", "translation": "پروردگار"}
  ]
}

// fill_blank
{
  "ayah_global_id": 2,
  "audio_url": "/audio/ayah/001002.mp3",
  "translation": "ستایش مخصوص خداوند...",
  "visible_text": "_____ لِلَّهِ رَبِّ _____",
  "blanks": [
    {"position": 0, "answer": "الْحَمْدُ"},
    {"position": 1, "answer": "الْعَالَمِينَ"}
  ],
  "options": ["الْحَمْدُ", "الْعَالَمِينَ", "الرَّحْمَنِ"]
}

// sentence_building
{
  "ayah_global_id": 5,
  "audio_url": "/audio/ayah/001005.mp3",
  "translation": "تنها تو را می‌پرستیم...",
  "words": ["إِيَّاكَ", "نَعْبُدُ", "وَإِيَّاكَ", "نَسْتَعِينُ"]
}

// multiple_choice
{
  "question": "ترجمه صحیح کدام است؟",
  "ayah_snippet": "إِيَّاكَ نَعْبُدُ",
  "correct_answer": "تنها تو را می‌پرستیم",
  "wrong_answers": ["مالک روز جزا", "خداوند بخشنده", "ما را هدایت کن"],
  "explanation": "إیّاک = تنها تو را"
}
```

### ۴.۲ QuestionFeedback (بازخورد)
```python
class QuestionFeedback(models.Model):
    question_id = models.PositiveIntegerField(db_index=True)
    user_id = models.PositiveIntegerField(db_index=True)
    is_positive = models.BooleanField()                     # 👍/👎
    created_at = models.DateTimeField(auto_now_add=True)
```

### ۴.۳ QuestionReport (گزارش)
```python
class QuestionReport(models.Model):
    question_id = models.PositiveIntegerField(db_index=True)
    user_id = models.PositiveIntegerField(db_index=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## ۵. Domain: Users (کاربران)

### ۵.۱ User (کاربر)
```python
class User(models.Model):
    class Platform(models.TextChoices):
        EITAA = 'eitaa', 'ایتا'
        TELEGRAM = 'telegram', 'تلگرام'
        BALE = 'bale', 'بله'
    
    platform = models.CharField(choices=Platform.choices)
    platform_user_id = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True)
    display_name = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['platform', 'platform_user_id']
```

---

## ۶. Domain: Progress (پیشرفت)

### ۶.۱ UserProgress (پیشرفت کاربر)
```python
class UserProgress(models.Model):
    user_id = models.PositiveIntegerField(unique=True)
    current_juz_id = models.PositiveIntegerField(null=True)
    current_stage_id = models.PositiveIntegerField(null=True)
    current_lesson_id = models.PositiveIntegerField(null=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### ۶.۲ LessonProgress (پیشرفت درس)
```python
class LessonProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'شروع نشده'
        IN_PROGRESS = 'in_progress', 'در حال انجام'
        COMPLETED = 'completed', 'تکمیل شده'
    
    user_id = models.PositiveIntegerField(db_index=True)
    lesson_id = models.PositiveIntegerField(db_index=True)
    status = models.CharField(choices=Status.choices)
    correct_count = models.PositiveSmallIntegerField(default=0)
    wrong_count = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user_id', 'lesson_id']
```

### ۶.۳ UserAnswer (پاسخ کاربر)
```python
class UserAnswer(models.Model):
    user_id = models.PositiveIntegerField(db_index=True)
    question_id = models.PositiveIntegerField(db_index=True)
    lesson_id = models.PositiveIntegerField(db_index=True)
    answer = models.JSONField()                             # پاسخ کاربر
    is_correct = models.BooleanField()
    time_spent_ms = models.PositiveIntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['user_id', 'answered_at']),
        ]
```

---

## ۷. نکات طراحی

### ۷.۱ جداسازی با ID به جای FK
```python
# ❌ نادرست - FK بین app های مختلف
class LessonQuestion(models.Model):
    question = models.ForeignKey('questions.Question', ...)

# ✅ درست - استفاده از ID
class LessonQuestion(models.Model):
    question_id = models.PositiveIntegerField(db_index=True)
```

### ۷.۲ Order با فاصله ۱۰۰۰۰
```python
# برای امکان درج بین آیتم‌ها
lesson1.order = 10000
lesson2.order = 20000
# درج جدید بین آن‌ها:
new_lesson.order = 15000
```

### ۷.۳ JSON برای انعطاف‌پذیری
- محتوای سوالات: انواع مختلف سوال با ساختارهای متفاوت
- محتوای درسنامه: Block-based content (آیه، گفتگو، گرامر)
- پاسخ کاربر: فرمت‌های مختلف بسته به نوع سوال
