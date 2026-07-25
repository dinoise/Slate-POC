"""API routes."""

from .agents import router as agents_router
from .demand_predictions import router as demand_predictions_router
from .dispatch_notes import router as dispatch_notes_router
from .dispatches import router as dispatches_router
from .recommendations import router as recommendations_router
from .resource_positions import router as resource_positions_router
from .resources import router as resources_router
from .settings import router as settings_router
from .tasks import router as tasks_router
from .users import router as users_router

__all__ = [
    "tasks_router",
    "resources_router",
    "agents_router",
    "dispatches_router",
    "dispatch_notes_router",
    "demand_predictions_router",
    "resource_positions_router",
    "recommendations_router",
    "settings_router",
    "users_router",
]
