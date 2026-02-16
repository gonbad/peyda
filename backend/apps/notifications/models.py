"""
Notifications Domain Models

لاگ نوتیفیکیشن‌های ارسال شده به کاربران.

قالب‌های نوتیفیکیشن پیدا:
- match_found: مچ جدید پیدا شد
- mawkab_approved: موکب تایید شد
- mawkab_rejected: موکب رد شد
- report_suspended: گزارش معلق شد
"""
from django.db import models
import uuid


class Notification(models.Model):
    """لاگ نوتیفیکیشن ارسال شده"""
    
    class Channel(models.TextChoices):
        MESSENGER = 'messenger', 'پیام‌رسان'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        SENT = 'sent', 'ارسال شده'
        FAILED = 'failed', 'ناموفق'
        BLOCKED = 'blocked', 'بلاک شده'
    
    class Template(models.TextChoices):
        MATCH_FOUND = 'match_found', 'مچ جدید'
        MAWKAB_APPROVED = 'mawkab_approved', 'تایید موکب'
        MAWKAB_REJECTED = 'mawkab_rejected', 'رد موکب'
        REPORT_SUSPENDED = 'report_suspended', 'معلق شدن گزارش'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.PositiveIntegerField(db_index=True, verbose_name='شناسه کاربر')
    
    template = models.CharField(
        max_length=100,
        choices=Template.choices,
        db_index=True,
        verbose_name='قالب پیام'
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        verbose_name='کانال'
    )
    payload = models.JSONField(
        default=dict,
        verbose_name='پارامترها',
        help_text='پارامترهای template مثل match_id, report_id'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت'
    )
    platform_message_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name='شناسه پیام در پلتفرم'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name='پیام خطا'
    )
    
    deep_link = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='Deep Link',
        help_text='مثلاً peyda://match/{matchId}'
    )
    
    metadata = models.JSONField(default=dict, verbose_name='متادیتا')
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ارسال')
    
    class Meta:
        verbose_name = 'نوتیفیکیشن'
        verbose_name_plural = 'نوتیفیکیشن‌ها'
        indexes = [
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_template_display()} -> {self.user_id} ({self.get_status_display()})"
