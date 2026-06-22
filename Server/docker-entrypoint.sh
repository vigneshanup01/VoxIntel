#!/bin/sh
set -e

python <<'PY'
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings

engine = create_engine(get_settings().database_url)

for _ in range(30):
    try:
        with engine.connect():
            break
    except OperationalError:
        time.sleep(1)
else:
    print("Database never became available", file=sys.stderr)
    sys.exit(1)
PY

alembic upgrade head

exec "$@"
