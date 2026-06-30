"""Celery application object.

Deliberately has no dependency on `whisper`/`torch`: the API process imports
this module (to enqueue jobs via `send_task`) without ever importing the
heavy ML stack that only the worker process needs. See `app/worker/tasks.py`
for the actual task implementation.
"""

import ssl

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("voxintel", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.task_default_queue = "transcription"
celery_app.conf.task_track_started = True
celery_app.conf.broker_transport_options = {"socket_connect_timeout": 10, "socket_timeout": 10}

# rediss:// (TLS) needs ssl_cert_reqs passed through; without this, some
# environments (e.g. Upstash) fail the TLS handshake inside the container.
if settings.redis_url.startswith("rediss://"):
    _ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.broker_use_ssl = _ssl_opts
    celery_app.conf.redis_backend_use_ssl = _ssl_opts
