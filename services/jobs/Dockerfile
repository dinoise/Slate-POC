# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/core/pyproject.toml services/core/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/notifications/pyproject.toml services/notifications/pyproject.toml
COPY services/shared-infra/pyproject.toml services/shared-infra/pyproject.toml
COPY services/jobs/pyproject.toml services/jobs/pyproject.toml

RUN uv sync --package slate-jobs --no-dev --no-install-workspace

COPY services/jobs/src ./services/jobs/src
COPY services/core/src ./services/core/src
COPY services/shared-infra/src ./services/shared-infra/src

RUN uv sync --package slate-jobs --no-dev

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# pandas/numpy necesitan estas libs en runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/services/jobs/src ./services/jobs/src
COPY --from=builder /app/services/core/src ./services/core/src
COPY --from=builder /app/services/shared-infra/src ./services/shared-infra/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/services/jobs/src:/app/services/core/src:/app/services/shared-infra/src"

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

ARG ENVIRONMENT=production
ARG LOG_LEVEL=INFO

ENV ENVIRONMENT=${ENVIRONMENT} \
    LOG_LEVEL=${LOG_LEVEL}

# No hay CMD por defecto — cada Cloud Run Job define su propio comando:
#   gcloud run jobs create slate-jobs-demand-refresh-dev --command="demand-refresh"
#   gcloud run jobs create slate-jobs-optimize-dev       --command="optimize"
