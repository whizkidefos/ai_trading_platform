import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load task modules from all registered Django app configs
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'execute_trade_every_hour': {
        'task': 'trading.tasks.execute_trade_task',
        'schedule': crontab(minute=0, hour='*'),  # Runs every hour
    },
}