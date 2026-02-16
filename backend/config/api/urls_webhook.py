"""
Webhook URL configuration for n8n webhooks.
This should only be accessible from the api-webhook container.
"""
from django.urls import path

from .views import health_check

urlpatterns = [
    path('health/', health_check, name='webhook-health-check'),
]
