from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'phone', 'role', 'mawkab_id', 'is_active', 'is_banned', 'created_at']
    list_filter = ['role', 'is_active', 'is_banned']
    search_fields = ['phone']
    readonly_fields = ['created_at', 'last_activity_at']
    
    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('phone', 'role', 'mawkab_id')
        }),
        ('وضعیت', {
            'fields': ('is_active', 'is_banned', 'ban_reason')
        }),
        ('محدودیت گزارش', {
            'fields': ('daily_report_count', 'daily_report_date')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'last_activity_at')
        }),
    )
