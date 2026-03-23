# ============ Stage 1: Builder ============
# Install Python dependencies in an isolated stage to keep the runtime image slim.
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============ Stage 2: Runtime Base ============
# Shared base for both API and Worker targets.
FROM python:3.11-slim AS runtime-base
WORKDIR /app

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code (NO .env files — secrets injected at runtime)
COPY apps/ ./apps/
COPY packages/ ./packages/

# Create required directories and set ownership
RUN mkdir -p /app/checkpoints /app/models && \
    chown -R appuser:appuser /app

# ============ Target: API ============
FROM runtime-base AS api
USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/api/v1/health')" || exit 1

CMD ["/bin/sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

# ============ Target: Worker ============
FROM runtime-base AS worker
USER appuser

CMD ["celery", "-A", "apps.api.celery_app", "worker", "--loglevel=info", "--queues=training", "--concurrency=2"]

# ============ Target: Flower ============
FROM runtime-base AS flower
USER appuser
EXPOSE 5555

CMD ["celery", "-A", "apps.api.celery_app", "flower", "--port=5555", "--url_prefix=/flower"]
