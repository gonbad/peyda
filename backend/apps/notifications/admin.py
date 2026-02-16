from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'template', 'channel', 'status', 'created_at', 'sent_at']
    list_filter = ['channel', 'status', 'template', 'created_at']
    search_fields = ['user_id', 'template']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
