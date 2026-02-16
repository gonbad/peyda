"""
URL configuration for webhook API (api-webhook container).
This is separate from the main API to prevent users from accessing webhook endpoints.
"""
from django.urls import path, include

urlpatterns = [
    path('api/v1/', include('config.api.urls_webhook')),
]
