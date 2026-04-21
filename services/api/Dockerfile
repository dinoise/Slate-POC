# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copiar archivos de workspace para que uv resuelva dependencias internas
COPY pyproject.toml uv.lock ./
COPY services/core/pyproject.toml services/core/pyproject.toml
COPY services/shared-infra/pyproject.toml services/shared-infra/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/notifications/pyproject.toml services/notifications/pyproject.toml
COPY services/jobs/pyproject.toml services/jobs/pyproject.toml

# Instalar solo las dependencias del servicio api (sin dev extras)
# --no-install-workspace evita instalar los paquetes locales aún (el código no está copiado)
RUN uv sync --package slate-api --no-dev --no-install-workspace

# Copiar código fuente
COPY services/api/src ./services/api/src
COPY services/core/src ./services/core/src
COPY services/shared-infra/src ./services/shared-infra/src

# Instalar paquetes locales en el venv ya creado
RUN uv sync --package slate-api --no-dev

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Instalar dependencias de sistema para PostGIS / GeoAlchemy2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar venv y código desde builder
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/services/api/src ./services/api/src
COPY --from=builder /app/services/core/src ./services/core/src
COPY --from=builder /app/services/shared-infra/src ./services/shared-infra/src

# Variables de entorno
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/services/api/src:/app/services/core/src:/app/services/shared-infra/src"

# Usuario no-root
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8080

# Build args para metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG ENVIRONMENT=production
ARG LOG_LEVEL=INFO

ENV ENVIRONMENT=${ENVIRONMENT} \
    LOG_LEVEL=${LOG_LEVEL}

CMD ["sh", "-c", "python -m uvicorn slate_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --forwarded-allow-ips='*'"]
