"""
API decorators including idempotency handling.
"""
from functools import wraps
from uuid import UUID
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status


def idempotent(func):
    """
    Decorator for idempotent endpoints.
    
    Checks for existing response with same idempotency_key.
    If found, returns cached response.
    Otherwise, executes function and stores response.
    
    Idempotency key can be provided via:
    - X-Idempotency-Key header
    - idempotency_key field in request body
    """
    
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        from config.api.models import IdempotencyRecord
        
        idem_key = (
            request.META.get('HTTP_X_IDEMPOTENCY_KEY') or
            request.data.get('idempotency_key')
        )
        
        if not idem_key:
            return Response(
                {
                    'error': 'Missing idempotency_key',
                    'code': 'IDEMPOTENCY_REQUIRED'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            idem_key = UUID(str(idem_key))
        except (ValueError, TypeError):
            return Response(
                {
                    'error': 'Invalid idempotency_key format',
                    'code': 'INVALID_IDEMPOTENCY_KEY'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = getattr(request.user, 'id', 0)
        endpoint = f"{request.method}:{request.path}"
        
        existing = IdempotencyRecord.objects.filter(
            key=idem_key,
            user_id=user_id
        ).first()
        
        if existing:
            return Response(
                existing.response_body,
                status=existing.response_status
            )
        
        with transaction.atomic():
            response = func(self, request, *args, **kwargs)
            
            IdempotencyRecord.objects.create(
                key=idem_key,
                user_id=user_id,
                endpoint=endpoint,
                response_status=response.status_code,
                response_body=response.data
            )
            
            return response
    
    return wrapper
