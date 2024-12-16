import os
from celery import Celery
from celery.schedules import crontab
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load task modules from all registered Django app configs
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'execute_trades': {
        'task': 'trading.tasks.execute_trade_task',
        'schedule': 60.0,  # Run every 60 seconds
    },
}


def notify_trade_update(message):
    """Send trade update notifications via WebSocket"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'trade_updates',
            {
                'type': 'trade_update',
                'message': message
            }
        )
    except Exception as e:
        print(f"Error sending trade notification: {str(e)}")