# الگوریتم مچینگ (Match Algorithm Proposal)

این سند پیشنهاد الگوریتم مچینگ برای سیستم پیدا را مستند می‌کند.

---

## ۱. خلاصه اجرایی

سیستم مچینگ پیدا از یک **الگوریتم امتیازدهی ترکیبی** استفاده می‌کند که متادیتا (سن، جنسیت، موقعیت) و در صورت وجود API آماده، شباهت چهره را ترکیب می‌کند.

### اصول کلیدی:
- **مچینگ متقابل:** گمشده فقط با پیداشده مچ می‌شود و برعکس
- **فقط گزارش‌های فعال:** گزارش‌های معلق و حل‌شده در مچینگ شرکت نمی‌کنند
- **نوتیفیکیشن یک‌طرفه:** فقط به گزارش قدیمی‌تر نوتیفیکیشن ارسال می‌شود
- **آستانه قابل تنظیم:** ادمین می‌تواند حد آستانه را تغییر دهد

---

## ۲. سیستم امتیازدهی

### ۲.۱ امتیاز کل (Total Score)

امتیاز کل از ۰ تا ۱۰۰ محاسبه می‌شود:

```
total_score = (metadata_score * metadata_weight) + (face_score * face_weight)
```

### ۲.۲ وزن‌دهی

| حالت | metadata_weight | face_weight |
|------|-----------------|-------------|
| بدون Face API | 1.0 | 0.0 |
| با Face API | 0.4 | 0.6 |

---

## ۳. امتیاز متادیتا (Metadata Score)

امتیاز متادیتا از ترکیب سه فاکتور محاسبه می‌شود:

### ۳.۱ امتیاز جنسیت (Gender Score)

| شرط | امتیاز |
|-----|--------|
| جنسیت یکسان | 100 |
| جنسیت متفاوت | 0 |
| یکی نامشخص | 50 |

**وزن:** 40%

### ۳.۲ امتیاز سن (Age Score)

```python
def calculate_age_score(age1, age2):
    if age1 is None or age2 is None:
        return 50  # نامشخص
    
    diff = abs(age1 - age2)
    
    if diff == 0:
        return 100
    elif diff <= 2:
        return 90
    elif diff <= 5:
        return 70
    elif diff <= 10:
        return 40
    else:
        return 10
```

**وزن:** 35%

### ۳.۳ امتیاز موقعیت (Location Score)

```python
def calculate_location_score(loc1, loc2):
    distance_km = haversine(loc1.lat, loc1.lng, loc2.lat, loc2.lng)
    
    if distance_km <= 0.5:
        return 100
    elif distance_km <= 1:
        return 90
    elif distance_km <= 2:
        return 70
    elif distance_km <= 5:
        return 50
    elif distance_km <= 10:
        return 30
    else:
        return 10
```

**وزن:** 25%

### ۳.۴ فرمول نهایی متادیتا

```python
metadata_score = (
    gender_score * 0.40 +
    age_score * 0.35 +
    location_score * 0.25
)
```

---

## ۴. امتیاز شباهت چهره (Face Score)

### ۴.۱ گزینه‌های API

| سرویس | هزینه | دقت | پیچیدگی |
|-------|-------|-----|---------|
| **DeepFace (پیشنهادی)** | رایگان | خوب | کم |
| AWS Rekognition | پولی | عالی | متوسط |
| Azure Face API | پولی | عالی | متوسط |
| InsightFace | رایگان | خوب | متوسط |

### ۴.۲ پیشنهاد: DeepFace

به واقع DeepFace یک کتابخانه Python رایگان و open-source است که می‌تواند:
- مقایسه دو چهره
- استخراج embedding چهره
- تشخیص سن و جنسیت (bonus)

```python
from deepface import DeepFace

def calculate_face_score(image1_url, image2_url):
    try:
        result = DeepFace.verify(
            img1_path=image1_url,
            img2_path=image2_url,
            model_name="VGG-Face",  # یا Facenet, ArcFace
            enforce_detection=False
        )
        
        # distance به similarity تبدیل می‌شود
        # distance کمتر = شباهت بیشتر
        distance = result['distance']
        threshold = result['threshold']
        
        if distance <= threshold * 0.5:
            return 100
        elif distance <= threshold:
            return 80
        elif distance <= threshold * 1.5:
            return 50
        else:
            return 20
            
    except Exception:
        return None  # چهره تشخیص داده نشد
```

### ۴.۳ مدیریت عکس‌های متعدد

اگر هر گزارش چند عکس داشته باشد:

```python
def calculate_best_face_score(images1, images2):
    scores = []
    
    for img1 in images1:
        for img2 in images2:
            score = calculate_face_score(img1, img2)
            if score is not None:
                scores.append(score)
    
    if not scores:
        return None  # هیچ چهره‌ای تشخیص داده نشد
    
    return max(scores)  # بهترین مچ
```

---

## ۵. آستانه‌ها (Thresholds)

### ۵.۱ آستانه نمایش مچ

| پارامتر | مقدار پیش‌فرض | توضیح |
|---------|---------------|-------|
| `MATCH_DISPLAY_THRESHOLD` | 40 | حداقل امتیاز برای نمایش مچ |
| `MATCH_NOTIFY_THRESHOLD` | 60 | حداقل امتیاز برای ارسال نوتیفیکیشن |

### ۵.۲ قابلیت تنظیم توسط ادمین

```python
# در تنظیمات سیستم
MATCH_SETTINGS = {
    'display_threshold': 40,
    'notify_threshold': 60,
    'use_face_recognition': False,  # فعال/غیرفعال کردن Face API
    'max_matches_per_report': 20,   # حداکثر تعداد مچ برای هر گزارش
}
```

---

## ۶. فرآیند مچینگ

### ۶.۱ زمان اجرا

مچینگ در دو زمان اجرا می‌شود:

1. **هنگام ثبت گزارش جدید:** گزارش جدید با تمام گزارش‌های فعال سمت مخالف مقایسه می‌شود
2. **Batch Job (اختیاری):** بازبینی دوره‌ای مچ‌ها (مثلاً هر ساعت)

### ۶.۲ الگوریتم

```python
def find_matches(new_report):
    # ۱. پیدا کردن گزارش‌های کاندید
    opposite_type = 'found' if new_report.type == 'lost' else 'lost'
    candidates = Report.objects.filter(
        type=opposite_type,
        status='active',
        gender__in=[new_report.gender, None]  # جنسیت یکسان یا نامشخص
    )
    
    matches = []
    
    for candidate in candidates:
        # ۲. محاسبه امتیاز
        score = calculate_total_score(new_report, candidate)
        
        # ۳. فیلتر بر اساس آستانه
        if score >= MATCH_DISPLAY_THRESHOLD:
            matches.append({
                'report': candidate,
                'score': score
            })
    
    # ۴. مرتب‌سازی بر اساس امتیاز
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    # ۵. محدود کردن تعداد
    matches = matches[:MAX_MATCHES_PER_REPORT]
    
    # ۶. ذخیره مچ‌ها
    for match in matches:
        Match.objects.create(
            report_new=new_report,
            report_old=match['report'],
            similarity_score=match['score'],
            status='pending'
        )
        
        # ۷. ارسال نوتیفیکیشن به گزارش قدیمی‌تر
        if match['score'] >= MATCH_NOTIFY_THRESHOLD:
            send_match_notification(match['report'], new_report)
    
    return matches
```

---

## ۷. ساختار داده Match

### ۷.۱ مدل Match

```python
class Match(models.Model):
    id = models.UUIDField(primary_key=True)
    
    # گزارش‌های مرتبط
    report_new = models.ForeignKey(Report, related_name='matches_as_new')
    report_old = models.ForeignKey(Report, related_name='matches_as_old')
    
    # امتیاز
    similarity_score = models.IntegerField()  # 0-100
    
    # وضعیت
    status = models.CharField(choices=[
        ('pending', 'در انتظار'),
        ('rejected', 'رد شده'),
    ])
    
    # متادیتا
    created_at = models.DateTimeField(auto_now_add=True)
    rejected_at = models.DateTimeField(null=True)
    rejected_by = models.ForeignKey(User, null=True)
    
    class Meta:
        unique_together = ['report_new', 'report_old']
```

### ۷.۲ API Response

```json
{
  "id": "match_123",
  "report_new_id": "report_456",
  "report_old_id": "report_789",
  "similarity_score": 75,
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "other_report": {
    "id": "report_789",
    "name": "علی",
    "age": 25,
    "gender": "male",
    "image_urls": ["..."],
    "location": {...},
    "contact_phone": "9123456789"
  }
}
```

---

## ۸. بهینه‌سازی عملکرد

### ۸.۱ ایندکس‌های پایگاه داده

```sql
CREATE INDEX idx_reports_active ON reports(type, status) WHERE status = 'active';
CREATE INDEX idx_reports_gender ON reports(gender);
CREATE INDEX idx_reports_location ON reports USING GIST(location);
```

### ۸.۲ کش Face Embeddings

برای جلوگیری از محاسبه مجدد:

```python
class ReportFaceEmbedding(models.Model):
    report = models.ForeignKey(Report)
    image_url = models.URLField()
    embedding = models.BinaryField()  # numpy array serialized
    created_at = models.DateTimeField(auto_now_add=True)
```

### ۸.۳ محدودیت‌ها

| پارامتر | مقدار |
|---------|-------|
| حداکثر کاندیدا برای بررسی | 1000 |
| حداکثر مچ برای هر گزارش | 20 |
| Timeout برای Face API | 5 ثانیه |

---

## ۹. فازبندی پیاده‌سازی

### فاز ۱ (MVP)
- مچینگ فقط بر اساس متادیتا
- آستانه ثابت (40)
- بدون Face Recognition

### فاز ۲
- اضافه کردن Face Recognition با DeepFace
- آستانه قابل تنظیم توسط ادمین
- کش Face Embeddings

### فاز ۳
- بهینه‌سازی عملکرد
- Batch Job برای بازبینی مچ‌ها
- گزارش‌دهی و تحلیل دقت الگوریتم

---

## ۱۰. تست و ارزیابی

### ۱۰.۱ معیارهای موفقیت

| معیار | هدف |
|-------|-----|
| Precision | > 70% |
| Recall | > 80% |
| زمان پاسخ | < 2 ثانیه |

### ۱۰.۲ تست‌های واحد

```python
def test_gender_score():
    assert calculate_gender_score('male', 'male') == 100
    assert calculate_gender_score('male', 'female') == 0
    assert calculate_gender_score('male', None) == 50

def test_age_score():
    assert calculate_age_score(25, 25) == 100
    assert calculate_age_score(25, 27) == 90
    assert calculate_age_score(25, 30) == 70
    assert calculate_age_score(25, 40) == 10

def test_location_score():
    # نقاط نزدیک
    assert calculate_location_score(
        Location(34.6416, 50.8746),
        Location(34.6420, 50.8750)
    ) == 100
```

---

## ۱۱. نتیجه‌گیری

این الگوریتم یک راه‌حل **مقیاس‌پذیر** و **قابل توسعه** برای مچینگ گزارش‌های پیدا ارائه می‌دهد:

- **فاز ۱:** ساده و سریع با متادیتا
- **فاز ۲:** دقیق‌تر با Face Recognition
- **قابل تنظیم:** ادمین می‌تواند آستانه‌ها را تغییر دهد
- **قابل اندازه‌گیری:** معیارهای مشخص برای ارزیابی

### اقدامات بعدی:
1. تایید این سند توسط تیم
2. پیاده‌سازی فاز ۱
3. جمع‌آوری داده برای تست
4. ارزیابی و تنظیم آستانه‌ها
