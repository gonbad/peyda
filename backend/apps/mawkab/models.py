"""
Mawkab Domain Models

این app شامل مدل‌های مربوط به موکب است:
- Mawkab (موکب)

نکته: FK فقط درون این app مجاز است.
به جای FK به User از owner_user_id استفاده می‌شود.
"""
from django.db import models


class Mawkab(models.Model):
    """موکب"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار تایید'
        APPROVED = 'approved', 'تایید شده'
        REJECTED = 'rejected', 'رد شده'
    
    name = models.CharField(
        max_length=200,
        verbose_name='نام موکب'
    )
    owner_name = models.CharField(
        max_length=200,
        verbose_name='نام صاحب موکب'
    )
    owner_phone = models.CharField(
        max_length=20,
        verbose_name='شماره تماس صاحب موکب'
    )
    owner_user_id = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        verbose_name='شناسه کاربر صاحب'
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
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت'
    )
    rejection_reason = models.TextField(
        null=True,
        blank=True,
        verbose_name='دلیل رد'
    )
    
    total_reports = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد کل گزارش‌ها'
    )
    resolved_reports = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد گزارش‌های حل شده'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تایید'
    )
    
    class Meta:
        verbose_name = 'موکب'
        verbose_name_plural = 'موکب‌ها'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['owner_user_id']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'
    
    @property
    def is_approved(self) -> bool:
        return self.status == self.Status.APPROVED
    
    @property
    def success_rate(self) -> float:
        """نرخ موفقیت (درصد حل‌شده‌ها)"""
        if self.total_reports == 0:
            return 0.0
        return (self.resolved_reports / self.total_reports) * 100
