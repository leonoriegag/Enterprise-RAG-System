# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

# --- Final Production Stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user for DevSecOps best practices
RUN groupadd -g 10001 appuser && \
    useradd -u 10000 -g appuser -s /bin/sh -m appuser

# Copy installed python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source, migrations, and seed examples
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY examples ./examples
COPY scripts ./scripts

# Ensure ownership by non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    LOG_LEVEL=INFO

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
