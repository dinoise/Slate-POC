# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/core/pyproject.toml services/core/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/notifications/pyproject.toml services/notifications/pyproject.toml
COPY services/jobs/pyproject.toml services/jobs/pyproject.toml

RUN uv sync --package slate-notifications --no-dev --no-install-workspace

COPY services/notifications/src ./services/notifications/src
COPY services/core/src ./services/core/src

RUN uv sync --package slate-notifications --no-dev

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/services/notifications/src ./services/notifications/src
COPY --from=builder /app/services/core/src ./services/core/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/services/notifications/src:/app/services/core/src"

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8001

ARG ENVIRONMENT=production
ARG LOG_LEVEL=INFO

ENV ENVIRONMENT=${ENVIRONMENT} \
    LOG_LEVEL=${LOG_LEVEL}

# IMPORTANTE: max-instances=1 en Cloud Run — el NotificationBroadcaster usa
# asyncio.Queue en memoria. Múltiples instancias perderían eventos.
CMD ["python", "-m", "uvicorn", "slate_notifications.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1"]
