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

# Copy API backend, ranking engine packages, scripts, crawler, and startup scripts
COPY apps/api apps/api
COPY packages/ packages/
COPY scripts/ scripts/
COPY website_scraping/ website_scraping/
COPY start.sh start.sh
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

ENV PORT=8000 \
    DATABASE_URL=sqlite:///newsreels.db \
    ALLOW_SQLITE_PROD=true \
    CORS_ORIGINS=*

EXPOSE 8000

CMD ["bash", "start.sh"]
