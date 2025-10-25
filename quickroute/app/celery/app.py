"""
Celery application configuration for QuickRoute.

Hybrid approach: Use Celery for distributed tasks alongside built-in periodic jobs.
"""

from celery import Celery
from ..settings import settings
from ..logging import logger

# Celery app instance
celery_app = Celery('fastdjango')

celery_app.conf.update(
    # Broker settings
    broker_url=getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),

    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'app.celery.tasks.*': {'queue': 'celery'},
        'app.celery.example_tasks.*': {'queue': 'default'},
    },

    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,

    # Task execution settings
    task_default_expires=3600,  # 1 hour
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_compression='gzip',

    # Result settings
    result_expires=3600,  # 1 hour
    result_compression='gzip',

    # Beat scheduler settings (if using Celery Beat)
    beat_schedule={},
)

# Optional: Configure from settings module if specified
celery_settings_module = getattr(settings, 'CELERY_SETTINGS_MODULE', None)
if celery_settings_module:
    celery_app.config_from_object(celery_settings_module)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app'])

def is_celery_available():
    """Check if Celery broker is available."""
    try:
        import redis
        broker_url = celery_app.conf.broker_url
        if 'redis://' in broker_url:
            host, port, db = broker_url.replace('redis://', '').split(':')
            r = redis.Redis(host=host, port=int(port), db=int(db), socket_connect_timeout=2)
            r.ping()
            return True
    except Exception as e:
        logger.warning(f"Celery broker not available: {e}")
        return False
    return False

if is_celery_available():
    logger.info("Celery initialized with Redis broker")
else:
    logger.warning("Celery broker not available - Celery tasks will be disabled")