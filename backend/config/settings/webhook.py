"""
Webhook API settings for Peyda project.
Uses separate ROOT_URLCONF for webhook endpoints only.
"""
from .development import *

ROOT_URLCONF = 'config.urls_webhook'
