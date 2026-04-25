"""Notifications service — standalone FastAPI app for SSE streams.

Service responsibilities:
    - Maintain a pg_notify LISTEN connection to receive assignment changes.
    - Broadcast raw payloads to in-memory subscriber queues.
    - Drain the outbox table as a durability fallback (every 30 s).
    - Serve SSE streams to adjuster and reporter clients.

Startup sequence (lifespan):
    1. ``listener.listen()`` task — asyncpg LISTEN on ``assignment_events``.
    2. ``outbox_poller.poll()`` task — periodic drain of undelivered events.

Shutdown sequence:
    Both tasks are cancelled and awaited before the process exits.

Auth:
    Google ID tokens are verified via ``slate_infra.auth``.  The
    ``accept_query_token=True`` flag allows ``?token=`` in addition to
    the ``Authorization`` header, which is required for ``EventSource``
    (the browser SSE API does not support custom headers).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slate_infra.auth import make_verify_google_token, verify_google_token

from .core.config import settings
from .core.database import async_session_maker
from .core.logging import setup_logging
from .routes import snapshot_router, stream_router
from .services import broadcaster as broadcaster_module
from .services import listener, outbox_poller

setup_logging(log_level=settings.effective_log_level, is_local=settings.is_local)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle: start and stop background tasks.

    Args:
        app: The FastAPI application instance (unused but required by FastAPI).

    Yields:
        Control to the running application between startup and shutdown.
    """
    dsn = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    bc = broadcaster_module.broadcaster

    tasks = [
        asyncio.create_task(
            listener.listen(dsn, bc),
            name="pg_notify_listener",
        ),
        asyncio.create_task(
            outbox_poller.poll(async_session_maker, bc),
            name="outbox_poller",
        ),
    ]

    yield

    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Register Google auth — SSE requires ?token= query param support
app.dependency_overrides[verify_google_token] = make_verify_google_token(
    client_ids=settings.google_client_ids,
    accept_query_token=True,
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        A dict with ``status`` and ``version`` keys.
    """
    return {"status": "healthy", "version": settings.VERSION}


app.include_router(stream_router)
app.include_router(snapshot_router)
