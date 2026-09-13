#!/usr/bin/env bash
set -e

# Ensure apps/api and root are discoverable on PYTHONPATH
export PYTHONPATH="/app:/app/apps/api:${PYTHONPATH}"

echo "Starting News Reels Backend on Render..."

# Apply database migrations if alembic is configured
if [ -f "apps/api/alembic.ini" ]; then
    echo "Applying Alembic database migrations..."
    alembic -c apps/api/alembic.ini upgrade head || true
fi

# Populate the published cards dataset if empty
echo "Checking and seeding published news database..."
python apps/api/scripts/seed_demo_cards.py || true

# Launch FastAPI web application with Uvicorn
echo "Launching FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --app-dir apps/api
