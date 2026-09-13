FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications and install
COPY apps/api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy API backend, ranking engine packages, and startup scripts
COPY apps/ apps/
COPY packages/ packages/
COPY start.sh start.sh
RUN chmod +x start.sh

ENV PORT=8000 \
    DATABASE_URL=sqlite:///newsreels.db \
    CORS_ORIGINS=*

EXPOSE 8000

CMD ["bash", "start.sh"]
