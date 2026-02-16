"""
Admins Domain Models

این app شامل مدل‌های مربوط به مدیران است.
ادمین‌ها از مدل User جنگو استفاده می‌کنند (django.contrib.auth.models.User)
و دسترسی‌های مختلف از طریق سیستم Permission جنگو مدیریت می‌شود.

دسترسی‌های سفارشی:
- can_manage_reports: مدیریت گزارش‌ها
- can_manage_mawkab: مدیریت موکب‌ها
- can_manage_users: مدیریت کاربران
- can_view_stats: مشاهده آمار
"""
from django.db import models
from django.contrib.auth.models import User


class AdminProfile(models.Model):
    """پروفایل تکمیلی برای ادمین‌ها"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_profile',
        verbose_name='کاربر'
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        verbose_name='شماره تلفن'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='یادداشت‌ها'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'پروفایل ادمین'
        verbose_name_plural = 'پروفایل‌های ادمین'
    
    def __str__(self):
        return f'پروفایل {self.user.username}'


class AdminPermission(models.Model):
    """دسترسی‌های سفارشی برای ادمین‌ها
    
    این مدل برای تعریف دسترسی‌های خاص پروژه استفاده می‌شود.
    """
    
    class PermissionType(models.TextChoices):
        MANAGE_REPORTS = 'manage_reports', 'مدیریت گزارش‌ها'
        MANAGE_MAWKAB = 'manage_mawkab', 'مدیریت موکب‌ها'
        MANAGE_USERS = 'manage_users', 'مدیریت کاربران'
        VIEW_STATS = 'view_stats', 'مشاهده آمار'
        SUSPEND_REPORT = 'suspend_report', 'تعلیق گزارش'
        VERIFY_MAWKAB = 'verify_mawkab', 'تایید موکب'
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_permissions',
        verbose_name='کاربر'
    )
    permission = models.CharField(
        max_length=20,
        choices=PermissionType.choices,
        verbose_name='دسترسی'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='اعطا شده توسط'
    )
    
    class Meta:
        verbose_name = 'دسترسی ادمین'
        verbose_name_plural = 'دسترسی‌های ادمین'
        unique_together = ['user', 'permission']
    
    def __str__(self):
        return f'{self.user.username} - {self.get_permission_display()}'


class AdminActivityLog(models.Model):
    """لاگ فعالیت‌های ادمین"""
    
    class ActionType(models.TextChoices):
        CREATE = 'create', 'ایجاد'
        UPDATE = 'update', 'ویرایش'
        DELETE = 'delete', 'حذف'
        APPROVE = 'approve', 'تأیید'
        REJECT = 'reject', 'رد'
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
        verbose_name='کاربر'
    )
    action = models.CharField(
        max_length=10,
        choices=ActionType.choices,
        verbose_name='عملیات'
    )
    model_name = models.CharField(
        max_length=50,
        verbose_name='نام مدل'
    )
    object_id = models.PositiveIntegerField(
        verbose_name='شناسه شیء'
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='جزئیات'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'لاگ فعالیت'
        verbose_name_plural = 'لاگ فعالیت‌ها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user} - {self.get_action_display()} {self.model_name}'
