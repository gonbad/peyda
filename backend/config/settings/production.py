"""
Production settings for Peyda project.
"""
import os
from .base import *

DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'peyda'),
        'USER': os.environ.get('DB_USER', 'peyda'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'peyda'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# CSRF Configuration for cross-domain requests
CSRF_TRUSTED_ORIGINS = [
    'https://peyda.eitala.dev',
    'https://www.peyda.eitala.dev',
]
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'None'

# Session Configuration for cross-domain requests
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'None'

# CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "https://peyda.eitala.dev",
    "https://www.peyda.eitala.dev",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# Security settings
SECURE_SSL_REDIRECT = os.environ.get('FORCE_SSL', 'False').lower() == 'true'
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True if SECURE_SSL_REDIRECT else False
SECURE_HSTS_PRELOAD = True if SECURE_SSL_REDIRECT else False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Trust proxy headers for SSL detection
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Static files and media - S3 configuration
STATIC_ROOT = '/app/staticfiles/'
MEDIA_ROOT = '/app/mediafiles/'

AWS_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.environ.get("S3_STATIC_BUCKET_NAME", "eitala-staticfiles")
AWS_S3_ENDPOINT_URL = os.environ.get(
    "S3_ENDPOINT_URL", "https://s3.kubit.ir"
)  # Your custom S3 endpoint
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_S3_VERIFY = os.environ.get('AWS_S3_VERIFY', 'True').lower() == 'true'


# Static files storage
STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/static/"

# Media files configuration
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "mediafiles"))


# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': os.environ.get('REDIS_PASSWORD'),
        }
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Sentry configuration for production
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
        
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=True,
            ),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=os.environ.get('SENTRY_ENVIRONMENT','dev'),
        release=os.environ.get('APP_VERSION', 'latest'),
        before_send_transaction=lambda event: None if event.get('transaction') == '/health/' else event,
    )
