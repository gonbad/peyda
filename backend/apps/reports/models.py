"""
Reports Domain Models

این app شامل مدل‌های مربوط به گزارش‌ها و مچ‌ها است:
- Report (گزارش گمشده/پیداشده)
- Match (تطبیق بین دو گزارش)

نکته: FK فقط درون این app مجاز است.
به جای FK به User از user_id و به جای FK به Mawkab از mawkab_id استفاده می‌شود.
"""
from django.db import models
import uuid


class Report(models.Model):
    """گزارش گمشده یا پیداشده"""
    
    class ReportType(models.TextChoices):
        LOST = 'lost', 'گمشده'
        FOUND = 'found', 'پیداشده'
    
    class Gender(models.TextChoices):
        MALE = 'male', 'مرد'
        FEMALE = 'female', 'زن'
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'فعال'
        RESOLVED = 'resolved', 'حل شده'
        SUSPENDED = 'suspended', 'معلق'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    report_type = models.CharField(
        max_length=10,
        choices=ReportType.choices,
        verbose_name='نوع گزارش'
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='وضعیت'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='نام فرد'
    )
    age = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='سن'
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        null=True,
        blank=True,
        verbose_name='جنسیت'
    )
    description = models.TextField(
        blank=True,
        verbose_name='توضیحات'
    )
    
    image_urls = models.JSONField(
        default=list,
        verbose_name='آدرس تصاویر',
        help_text='لیست URL تصاویر (حداکثر ۵ عکس)'
    )
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name='عرض جغرافیایی'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name='طول جغرافیایی'
    )
    address = models.TextField(
        blank=True,
        verbose_name='آدرس متنی'
    )
    
    contact_phone = models.CharField(
        max_length=20,
        verbose_name='شماره تماس'
    )
    
    user_id = models.PositiveIntegerField(
        db_index=True,
        verbose_name='شناسه کاربر ثبت‌کننده'
    )
    mawkab_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='شناسه موکب',
        help_text='اگر توسط موکب ثبت شده باشد'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان حل شدن'
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان معلق شدن'
    )
    suspended_by_admin_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='شناسه ادمین معلق‌کننده'
    )
    
    class Meta:
        verbose_name = 'گزارش'
        verbose_name_plural = 'گزارش‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['user_id']),
            models.Index(fields=['mawkab_id']),
            models.Index(fields=['gender']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.get_report_type_display()}: {self.name} ({self.get_status_display()})'
    
    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE
    
    @property
    def image_count(self) -> int:
        return len(self.image_urls) if self.image_urls else 0


class Match(models.Model):
    """تطبیق بین دو گزارش (گمشده و پیداشده)"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        REJECTED = 'rejected', 'رد شده'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    report_lost = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='matches_as_lost',
        verbose_name='گزارش گمشده'
    )
    report_found = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='matches_as_found',
        verbose_name='گزارش پیداشده'
    )
    
    similarity_score = models.PositiveSmallIntegerField(
        verbose_name='امتیاز شباهت (۰-۱۰۰)'
    )
    
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت'
    )
    
    notified_report_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='شناسه گزارشی که نوتیفیکیشن دریافت کرد'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان رد'
    )
    rejected_by_user_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='شناسه کاربر رد‌کننده'
    )
    
    class Meta:
        verbose_name = 'تطبیق'
        verbose_name_plural = 'تطبیق‌ها'
        ordering = ['-similarity_score', '-created_at']
        unique_together = ['report_lost', 'report_found']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['similarity_score']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f'مچ: {self.report_lost.name} <-> {self.report_found.name} ({self.similarity_score}%)'
    
    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING
