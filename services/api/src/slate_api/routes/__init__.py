"""API routes."""
from .adjuster_positions import router as adjuster_positions_router
from .adjusters import router as adjusters_router
from .assignments import router as assignments_router
from .demand_predictions import router as demand_predictions_router
from .incidents import router as incidents_router
from .map import router as map_router
from .notifications import router as notifications_router
from .recommendations import router as recommendations_router
from .settings import router as settings_router
from .users import router as users_router

__all__ = [
    "incidents_router",
    "adjusters_router",
    "assignments_router",
    "map_router",
    "demand_predictions_router",
    "adjuster_positions_router",
    "recommendations_router",
    "settings_router",
    "users_router",
    "notifications_router",
]
