"""
Celery configuration for asynchronous tasks.

Celery allows executing background tasks such as:
- Video processing
- Thumbnail generation
- Bulk email sending
- Temporary file cleanup
"""

import os 
from celery import Celery

# Set the default Django settings module for the Celery program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Create a Celery application instance with the name 'config'
app = Celery('config')

# Load configuration from Django settings with the CELERY namespace
# This means all Celery settings in Django should be prefixed with CELERY_
# Ex: CELERY_BROKER_URL -> app.conf.broker_url
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks in all installed Django apps
# Celery will look for tasks.py files in each app
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for test the Celery."""
    print(f'Request: {self.request!r}')