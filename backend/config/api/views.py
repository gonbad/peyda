"""
API views (non-viewset endpoints).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    
    Returns:
        200 OK if service is healthy
        503 Service Unavailable if unhealthy
    """
    health = {
        'status': 'healthy',
        'checks': {}
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health['checks']['database'] = 'ok'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['checks']['database'] = str(e)
    
    # Check Redis (optional)
    try:
        from infrastructure.bootstrap import get_container
        from infrastructure.cache import Cache
        container = get_container()
        cache = container.get(Cache)
        cache.set('health_check', 'ok', ttl=10)
        if cache.get('health_check') == 'ok':
            health['checks']['cache'] = 'ok'
        else:
            health['checks']['cache'] = 'read failed'
    except Exception as e:
        health['checks']['cache'] = f'error: {e}'
    
    status_code = 200 if health['status'] == 'healthy' else 503
    return Response(health, status=status_code)
