#!/bin/sh
set -e

# Bring this service's own database up to the latest schema before the app
# starts. Alembic uses a sync (psycopg2) driver; the app then serves with
# asyncpg. Because migrations run here, on_startup only needs to seed.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
