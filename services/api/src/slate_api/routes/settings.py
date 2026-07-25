"""Settings routes — runtime configuration (provider switching, etc.)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from slate_core.geospatial.factory import _SUPPORTED_PROVIDERS

from ..core.config import settings
from ..core.provider_registry import switch_provider

# Providers available for runtime switching.
_ENABLED_PROVIDERS = list(_SUPPORTED_PROVIDERS)

router = APIRouter(prefix="/settings", tags=["settings"])


# Providers that use OSM speed data (maxspeed tags) for realistic travel times
# but do not support real-time or predicted traffic feeds.
_SPEED_AWARE_PROVIDERS = {"valhalla"}


class ProviderInfo(BaseModel):
    """Active routing provider info."""

    provider: str
    supports_traffic: bool
    speed_aware: bool = False  # Uses OSM maxspeed data but no live traffic
    available_providers: list[str]


class ProviderUpdate(BaseModel):
    """Request body for switching provider."""

    provider: str


@router.get(
    "/provider",
    response_model=ProviderInfo,
    summary="Get active routing provider",
)
async def get_provider(request: Request) -> ProviderInfo:
    """Return the currently active routing provider and available options."""
    active = request.app.state.routing_provider
    return ProviderInfo(
        provider=active.provider_name,
        supports_traffic=active.supports_traffic,
        speed_aware=active.provider_name in _SPEED_AWARE_PROVIDERS,
        available_providers=_ENABLED_PROVIDERS,
    )


@router.put(
    "/provider",
    response_model=ProviderInfo,
    summary="Switch active routing provider",
)
async def update_provider(body: ProviderUpdate, request: Request) -> ProviderInfo:
    """
    Replace the active routing provider at runtime.

    The switch is atomic — in-flight requests that already hold a reference to
    the old provider complete normally; new requests get the updated one.

    Raises:
        422: If *provider* is not a recognised provider name.
    """
    if body.provider not in _ENABLED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unknown or unavailable provider '{body.provider}'. "
                f"Available: {sorted(_ENABLED_PROVIDERS)}"
            ),
        )
    new_provider = await switch_provider(body.provider, settings)
    # Keep app.state in sync so subsequent get_active_provider() calls see the new one.
    request.app.state.routing_provider = new_provider
    return ProviderInfo(
        provider=new_provider.provider_name,
        supports_traffic=new_provider.supports_traffic,
        speed_aware=new_provider.provider_name in _SPEED_AWARE_PROVIDERS,
        available_providers=_ENABLED_PROVIDERS,
    )
