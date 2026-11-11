#!/usr/bin/env bash
set -e

# Ensure apps/api and root are discoverable on PYTHONPATH
export PYTHONPATH="/app:/app/apps/api:${PYTHONPATH}"

echo "Starting NEWZZ Backend on Render..."

# Apply database migrations if alembic is configured (fail fast without error suppression)
if [ -f "apps/api/alembic.ini" ]; then
    echo "Applying Alembic database migrations..."
    alembic -c apps/api/alembic.ini upgrade head
fi

# Launch FastAPI web application with Uvicorn (Web API service only)
echo "Launching FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --app-dir apps/api
