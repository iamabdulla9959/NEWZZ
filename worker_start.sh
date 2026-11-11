#!/usr/bin/env bash
set -e

# Ensure apps/api, apps/worker, packages, and root are discoverable on PYTHONPATH in both Docker and Native environments
export PYTHONPATH=".:/app:apps/api:/app/apps/api:apps/worker:/app/apps/worker:packages:/app/packages:${PYTHONPATH}"

echo "Starting NEWZZ Background Ingestion Worker on Render..."

# Execute canonical background ingestion scheduler
exec python apps/worker/worker/main.py
