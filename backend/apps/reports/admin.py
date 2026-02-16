from django.contrib import admin
from .models import Report, Match


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'status', 'gender', 'age', 'created_at']
    list_filter = ['report_type', 'status', 'gender', 'created_at']
    search_fields = ['name', 'description', 'contact_phone']
    readonly_fields = ['id', 'created_at', 'updated_at', 'resolved_at', 'suspended_at']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('id', 'report_type', 'status', 'name', 'age', 'gender')
        }),
        ('توضیحات و تصاویر', {
            'fields': ('description', 'image_urls')
        }),
        ('موقعیت', {
            'fields': ('latitude', 'longitude', 'address')
        }),
        ('تماس', {
            'fields': ('contact_phone', 'user_id', 'mawkab_id')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'suspended_at', 'suspended_by_admin_id')
        }),
    )


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_lost', 'report_found', 'similarity_score', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['report_lost__name', 'report_found__name']
    readonly_fields = ['id', 'created_at', 'rejected_at']
    
    fieldsets = (
        ('گزارش‌ها', {
            'fields': ('id', 'report_lost', 'report_found')
        }),
        ('امتیاز و وضعیت', {
            'fields': ('similarity_score', 'status')
        }),
        ('نوتیفیکیشن', {
            'fields': ('notified_report_id',)
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'rejected_at', 'rejected_by_user_id')
        }),
    )
