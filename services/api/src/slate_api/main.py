"""FastAPI main application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core import close_db, get_logger, init_db, settings, setup_logging, verify_google_token
from .core.exceptions import AppException
from .core.provider_registry import init_provider
from .routes import (
    adjuster_positions_router,
    adjusters_router,
    assignments_router,
    demand_predictions_router,
    incidents_router,
    recommendations_router,
    settings_router,
    users_router,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    await init_db()
    app.state.routing_provider = init_provider(settings)
    logger.info("Routing provider initialised: %s", app.state.routing_provider.provider_name)

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema de asignación dinámica de ajustadores de seguros",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_local else None,
    redoc_url="/redoc" if settings.is_local else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.VERSION}


# Auth dependency applied to all API routers — /health is excluded (no prefix)
_auth = [Depends(verify_google_token)]

# Register routers
app.include_router(incidents_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(adjusters_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(assignments_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(demand_predictions_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(adjuster_positions_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(recommendations_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)
app.include_router(users_router, prefix=settings.API_V1_PREFIX, dependencies=_auth)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
