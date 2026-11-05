import os
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "multicloud_dr_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.replication.engine"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max for massive multi-gigabyte transfers
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# For testing or environments without Redis:
if os.environ.get("CELERY_ALWAYS_EAGER", "False").lower() in ("true", "1"):
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

