"""
URL configuration for Peyda project.

نکته: URLها در سطح پروژه تعریف می‌شوند، نه در سطح app.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('config.api.urls')),
]
