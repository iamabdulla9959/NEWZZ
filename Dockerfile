FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/apps/api:/app/apps/worker:/app/packages:.:apps/api:apps/worker:packages"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications preserving directory hierarchy for relative requirements resolution (-r ../api/requirements.txt)
COPY apps/api/requirements.txt apps/api/requirements.txt
COPY apps/worker/requirements.txt apps/worker/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt && \
    pip install --no-cache-dir -r apps/worker/requirements.txt

# Copy API backend, worker, ranking engine packages, scripts, crawler, and startup scripts
COPY apps/api apps/api
COPY apps/worker apps/worker
COPY packages/ packages/
COPY scripts/ scripts/
COPY website_scraping/ website_scraping/
COPY start.sh start.sh
COPY worker_start.sh worker_start.sh
RUN sed -i 's/\r$//' start.sh worker_start.sh && chmod +x start.sh worker_start.sh

ENV PORT=8000 \
    DATABASE_URL=sqlite:///newsreels.db \
    ALLOW_SQLITE_PROD=true \
    CORS_ORIGINS=*

EXPOSE 8000

CMD ["bash", "start.sh"]
