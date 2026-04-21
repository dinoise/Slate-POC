"""Notifications service — standalone FastAPI app for SSE streams."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slate_infra.auth import make_verify_google_token, verify_google_token

from .core.config import settings
from .core.logging import setup_logging
from .routes import stream_router
from .services.broadcaster import start_listener, stop_listener

setup_logging(log_level=settings.effective_log_level, is_local=settings.is_local)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await start_listener(app)
    yield
    await stop_listener(app)


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
    return {"status": "healthy", "version": settings.VERSION}


app.include_router(stream_router)
