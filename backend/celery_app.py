"""Celery application configuration for background scan workers."""

from celery import Celery
from config import Config


celery_app = Celery(
    "dfas",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue=Config.SCAN_QUEUE_NAME,
    imports=("tasks",),
)
