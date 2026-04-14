# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Despacho** — incident dispatch and adjuster assignment system. Monorepo with Python backend services and Vue 3 frontend apps.

## Package Manager

- **Python**: `uv` (workspace). Always prefix Python commands with `uv run`.
- **Frontend**: `pnpm` (workspace). Always prefix frontend commands with `pnpm`.

## Commands

```bash
# Install all dependencies
uv sync

# Run API (development)
uv run uvicorn slate_api.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations (run from repo root)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
uv run alembic downgrade -1

# Tests
uv run pytest                          # all services
uv run pytest services/api/            # single service

# Lint / format
uv run ruff check services/
uv run ruff format services/

# Docker (local dev services: postgres, redis)
docker compose up -d
docker compose down -v                 # destroy volumes (reset DB)

# Docker with optional tools (pgadmin, jupyter)
docker compose --profile tools up -d

# Docker with routing backends
docker compose --profile osrm up -d
docker compose --profile valhalla up -d
```

## Structure

```
slate-poc/
├── services/
│   ├── api/            # FastAPI — main HTTP API (slate_api)
│   ├── core/           # Shared library — geospatial + optimization (slate_core)
│   ├── notifications/  # pg_notify LISTEN + SSE broadcaster (slate_notifications)
│   └── jobs/           # Background jobs — demand prediction (slate_jobs)
├── apps/
│   ├── admin/          # Vue 3 — user CRUD
│   ├── reporter/       # Vue 3 — incident reporting
│   └── adjuster/       # Vue 3 — real-time adjuster view with map
├── alembic/            # Migrations (shared, covers services/api models)
├── docs/               # Architecture diagrams and proposals
└── docker-compose.yml
```

## Architecture (services/api)

Layered FastAPI application:

| Layer | Path | Responsibility |
|---|---|---|
| Models | `models/` | SQLAlchemy 2.0 async ORM |
| Repositories | `repositories/` | DB queries. `BaseRepository[T]` generic CRUD |
| Services | `services/` | Business logic. Orchestrates repositories |
| Routes | `routes/` | FastAPI routers, thin — call services, return schemas |
| Schemas | `schemas/` | Pydantic v2 — separate `Create`, `Update`, `Read` variants |
| Core | `core/` | config, database, exceptions, logging, notifier |

## Database

PostgreSQL 16 + PostGIS 3.x. Alembic manages migrations.

Geometry columns use `spatial_index=False` + explicit `Index(..., postgresql_using="gist")` in `__table_args__` — avoids duplicate GIST indexes during Alembic autogenerate.

Alembic `env.py` uses `alembic_helpers` from GeoAlchemy2 and an `include_object` filter to exclude PostGIS system schemas/tables from autogenerate.

## Notifications (SSE + pg_notify)

`services/notifications` must run with **`max-instances=1`** on Cloud Run — `NotificationBroadcaster` uses in-memory `asyncio.Queue` per adjuster; multiple instances would drop events. For scale, replace with Redis Pub/Sub.

Flow: `PostgreSQL trigger → pg_notify → asyncpg LISTEN → NotificationBroadcaster → asyncio.Queue → SSE → browser EventSource`
