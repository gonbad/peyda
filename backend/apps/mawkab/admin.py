from django.contrib import admin
from .models import Mawkab


@admin.register(Mawkab)
class MawkabAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner_name', 'status', 'total_reports', 'resolved_reports', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'owner_name', 'owner_phone']
    readonly_fields = ['total_reports', 'resolved_reports', 'created_at', 'updated_at', 'approved_at']
    
    fieldsets = (
        ('اطلاعات موکب', {
            'fields': ('name', 'owner_name', 'owner_phone', 'owner_user_id')
        }),
        ('موقعیت', {
            'fields': ('latitude', 'longitude', 'address')
        }),
        ('وضعیت', {
            'fields': ('status', 'rejection_reason', 'approved_at')
        }),
        ('آمار', {
            'fields': ('total_reports', 'resolved_reports')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at')
        }),
    )
