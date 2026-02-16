"""
Development settings for Peyda project.
"""
from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'peyda',
        'USER': 'peyda',
        'PASSWORD': 'peyda',
        'HOST': 'db',
        'PORT': '5432',
    }
}
STATIC_URL = "/static/"
STATIC_ROOT = os.getenv("STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))
