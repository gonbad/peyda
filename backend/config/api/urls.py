"""
API URL configuration for Peyda.
Based on OpenAPI.yaml endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import health_check
from .viewsets import (
    AuthViewSet,
    ReportsViewSet,
    MatchesViewSet,
    MawkabViewSet,
    DashboardViewSet,
)

router = DefaultRouter()
router.register(r'reports', ReportsViewSet, basename='reports')
router.register(r'matches', MatchesViewSet, basename='matches')

urlpatterns = [
    path('health/', health_check, name='health-check'),
    
    # Auth endpoints (no auth required)
    path('auth/send-otp', AuthViewSet.as_view({'post': 'send_otp'}), name='auth-send-otp'),
    path('auth/verify-otp', AuthViewSet.as_view({'post': 'verify_otp'}), name='auth-verify-otp'),
    path('auth/resend-otp', AuthViewSet.as_view({'post': 'resend_otp'}), name='auth-resend-otp'),
    
    # Mawkab endpoints
    path('mawkab', MawkabViewSet.as_view({'get': 'list', 'post': 'create', 'put': 'update'}), name='mawkab'),
    path('mawkab/stats', MawkabViewSet.as_view({'get': 'stats'}), name='mawkab-stats'),
    
    # Dashboard stats
    path('dashboard/stats', DashboardViewSet.as_view({'get': 'list'}), name='dashboard-stats'),
    
    # Router URLs (reports, matches)
    path('', include(router.urls)),
]
