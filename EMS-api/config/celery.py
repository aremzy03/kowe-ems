"""
Celery application for the EMS API.

Workers start with ``celery -A config worker`` (see docker-compose
``worker``). Django settings under the ``CELERY_`` prefix are loaded
from ``config.settings``. Tasks are autodiscovered from installed apps;
the notification task lives in ``communications.tasks``.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('ems')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
