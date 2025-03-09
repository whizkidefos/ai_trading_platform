"""
Development settings for the AI Trading Platform.
This file extends the base settings and disables Celery for local development.
"""

from .settings import *

# Disable Celery for local development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory channel layer for development
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# Ensure debug is enabled
DEBUG = True
