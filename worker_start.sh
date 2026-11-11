#!/usr/bin/env bash
set -e

# Ensure apps/api, apps/worker, and root are discoverable on PYTHONPATH
export PYTHONPATH="/app:/app/apps/api:/app/apps/worker:${PYTHONPATH}"

echo "Starting NEWZZ Background Ingestion Worker on Render..."

# Execute canonical background ingestion scheduler
exec python apps/worker/worker/main.py
