"""Celery application object.

Deliberately has no dependency on `whisper`/`torch`: the API process imports
this module (to enqueue jobs via `send_task`) without ever importing the
heavy ML stack that only the worker process needs. See `app/worker/tasks.py`
for the actual task implementation.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("voxintel", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.task_default_queue = "transcription"
celery_app.conf.task_track_started = True
celery_app.conf.broker_transport_options = {"socket_connect_timeout": 3, "socket_timeout": 3}
