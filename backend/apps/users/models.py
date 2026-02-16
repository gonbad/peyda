"""
Users Domain Models

این app شامل مدل‌های مربوط به کاربران است:
- User (کاربر با احراز هویت OTP)

نکته: FK فقط درون این app مجاز است.
به جای FK به Mawkab از mawkab_id استفاده می‌شود.
"""
from django.db import models


class User(models.Model):
    """کاربر با احراز هویت OTP"""
    
    class Role(models.TextChoices):
        USER = 'user', 'کاربر عادی'
        MAWKAB_OWNER = 'mawkab_owner', 'صاحب موکب'
        ADMIN = 'admin', 'ادمین'
    
    phone = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name='شماره تماس'
    )
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        verbose_name='نقش'
    )
    mawkab_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='شناسه موکب',
        help_text='اگر کاربر صاحب موکب است'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_banned = models.BooleanField(default=False, verbose_name='مسدود')
    ban_reason = models.TextField(null=True, blank=True, verbose_name='دلیل مسدودیت')
    
    daily_report_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='تعداد گزارش امروز'
    )
    daily_report_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='تاریخ شمارش گزارش روزانه'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['last_activity_at']),
            models.Index(fields=['mawkab_id']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f'{self.phone} ({self.get_role_display()})'
    
    @property
    def is_authenticated(self) -> bool:
        """Required for DRF IsAuthenticated permission."""
        return True
    
    @property
    def is_anonymous(self) -> bool:
        """Required for DRF."""
        return False
    
    @property
    def is_verified_mawkab_owner(self) -> bool:
        """آیا صاحب موکب تایید شده است"""
        return self.role == self.Role.MAWKAB_OWNER and self.mawkab_id is not None
    
    @property
    def is_admin(self) -> bool:
        """آیا ادمین است"""
        return self.role == self.Role.ADMIN
