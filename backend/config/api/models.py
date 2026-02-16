"""
API models including Idempotency tracking.
"""
from django.db import models
import uuid


class IdempotencyRecord(models.Model):
    """
    Record of idempotent request results.
    Stores the response for duplicate request detection.
    """
    
    key = models.UUIDField(unique=True, db_index=True)
    user_id = models.PositiveIntegerField(db_index=True)
    endpoint = models.CharField(max_length=200)
    
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_idempotency_record'
        indexes = [
            models.Index(fields=['key', 'user_id']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Idempotency Record'
        verbose_name_plural = 'Idempotency Records'
    
    def __str__(self):
        return f"{self.key} - {self.endpoint}"
