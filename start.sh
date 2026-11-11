#!/usr/bin/env bash
set -e

# Ensure apps/api and root are discoverable on PYTHONPATH in both Docker and Native environments
export PYTHONPATH=".:/app:apps/api:/app/apps/api:${PYTHONPATH}"

echo "Starting NEWZZ Backend on Render..."

# Apply database migrations if alembic is configured and postgresql is target
if [ -f "apps/api/alembic.ini" ] && [[ "${DATABASE_URL}" == postgres* ]]; then
    echo "Applying Alembic database migrations on PostgreSQL..."
    alembic -c apps/api/alembic.ini upgrade head || echo "Alembic migration notice, proceeding with startup..."
fi

# Launch FastAPI web application with Uvicorn (Web API service only)
echo "Launching FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --app-dir apps/api
