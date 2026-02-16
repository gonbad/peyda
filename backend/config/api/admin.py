from django.contrib import admin
from .models import IdempotencyRecord


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ['key', 'user_id', 'endpoint', 'response_status', 'created_at']
    list_filter = ['response_status', 'created_at']
    search_fields = ['key', 'endpoint']
    readonly_fields = ['key', 'user_id', 'endpoint', 'response_status', 'response_body', 'created_at']
    ordering = ['-created_at']
