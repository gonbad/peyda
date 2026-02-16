"""
Base settings for Peyda project.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,192.168.68.224').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'corsheaders',
    'rest_framework',
    
    # Local apps
    'apps.users',
    'apps.admins',
    'apps.notifications',
    'apps.reports',
    'apps.mawkab',
    'config.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'peyda'),
        'USER': os.environ.get('DB_USER', 'peyda'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'peyda'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'config.api.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.openapi.AutoSchema',
}

# CORS settings - allow all origins in development, override in production
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-idempotency-key',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Infrastructure settings
_redis_host = os.environ.get('REDIS_HOST', 'localhost')
_redis_port = os.environ.get('REDIS_PORT', '6379')
_redis_password = os.environ.get('REDIS_PASSWORD', '')
REDIS_URL = os.environ.get('REDIS_URL', f'redis://:{_redis_password}@{_redis_host}:{_redis_port}/0' if _redis_password else f'redis://{_redis_host}:{_redis_port}/0')


# n8n webhook for notifications (OTP, match notifications, etc.)
N8N_NOTIFICATION_WEBHOOK = os.environ.get('N8N_NOTIFICATION_WEBHOOK', '')

# Peyda specific settings
DAILY_REPORT_LIMIT = int(os.environ.get('DAILY_REPORT_LIMIT', 3))  # برای کاربران عادی
MATCH_DISPLAY_THRESHOLD = int(os.environ.get('MATCH_DISPLAY_THRESHOLD', 40))
MATCH_NOTIFY_THRESHOLD = int(os.environ.get('MATCH_NOTIFY_THRESHOLD', 60))
MAX_MATCHES_PER_REPORT = int(os.environ.get('MAX_MATCHES_PER_REPORT', 20))
MAX_IMAGES_PER_REPORT = int(os.environ.get('MAX_IMAGES_PER_REPORT', 5))
DEFAULT_LOCATION_LAT = float(os.environ.get('DEFAULT_LOCATION_LAT', 34.6416))  # بلوار پیامبر اعظم قم
DEFAULT_LOCATION_LNG = float(os.environ.get('DEFAULT_LOCATION_LNG', 50.8746))

# Webhook secret for n8n
N8N_WEBHOOK_SECRET = os.environ.get('N8N_WEBHOOK_SECRET', 'dev-webhook-secret')

# OTP Auth settings
OTP_EXPIRY_SECONDS = int(os.environ.get('OTP_EXPIRY_SECONDS', 300))  # 5 minutes
OTP_MAX_ATTEMPTS = int(os.environ.get('OTP_MAX_ATTEMPTS', 3))
OTP_MAX_RESENDS = int(os.environ.get('OTP_MAX_RESENDS', 3))
JWT_EXPIRY_DAYS = int(os.environ.get('JWT_EXPIRY_DAYS', 30))

# Sentry configuration
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
            environment=os.environ.get('ENVIRONMENT', 'development'),
        )
    except ImportError:
        pass  # sentry-sdk not installed
