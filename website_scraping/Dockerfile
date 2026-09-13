FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install wheels
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configuration
COPY bot/ ./bot/
COPY feeds.yaml .
COPY main.py .

# Create persistent storage directory for SQLite database
RUN mkdir -p /data

# Default environment configuration
ENV DB_PATH=/data/news_aggregator.db \
    FETCH_INTERVAL_MIN=15

CMD ["python", "main.py"]
