# NEXUS API (FastAPI + quant/AI/backtesting/paper-trading packages).
# Build context: repository root (needs services/ and database/).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/services:/app/services/api

WORKDIR /app
COPY services/api/requirements.txt services/api/requirements.txt
RUN pip install -r services/api/requirements.txt

COPY services/ services/
COPY database/ database/

RUN useradd --create-home --uid 10001 nexus && mkdir -p /app/data && chown -R nexus:nexus /app/data
USER nexus

# Bind inside the container; docker-compose publishes the port on 127.0.0.1 only.
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    NEXUS_ENV_FILE=/app/data/.env \
    NEXUS_SECRETS_FILE=/app/data/.secrets.env

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

WORKDIR /app/services
CMD ["python", "-m", "app.cli", "serve"]
