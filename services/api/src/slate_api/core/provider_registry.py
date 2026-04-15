"""Runtime routing-provider registry.

Holds the single active ``RoutingProvider`` instance for the lifetime of the
process.  Switching providers at runtime (via ``PUT /api/v1/settings/provider``)
replaces this instance without restarting the server.

Usage
-----
Inject via FastAPI ``Depends``::

    from ..core.provider_registry import get_active_provider, ProviderDep

    async def my_endpoint(provider: ProviderDep) -> ...:
        result = await provider.route(...)

The registry is initialised in ``main.py`` lifespan using the value of
``settings.TRAFFIC_PROVIDER`` as the default.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, Request

from slate_core.geospatial.base import RoutingProvider
from slate_core.geospatial.factory import get_routing_provider

from .config import Settings

# Module-level active provider — replaced atomically on provider switch.
_active_provider: RoutingProvider | None = None
_lock = asyncio.Lock()


def init_provider(settings: Settings) -> RoutingProvider:
    """Instantiate and register the provider configured in *settings*.

    Called once from the ``lifespan`` context manager at startup.
    """
    global _active_provider
    _active_provider = get_routing_provider(settings)
    return _active_provider


async def switch_provider(name: str, settings: Settings) -> RoutingProvider:
    """Replace the active provider with *name*.

    Thread-safe: acquires ``_lock`` before swapping the reference so that
    in-flight requests that already hold a reference to the old provider
    complete normally while new requests get the updated one.

    Args:
        name: Provider identifier — must be one of the values supported by
              ``get_routing_provider`` (e.g. ``"osrm"``, ``"google"``).
        settings: Application settings used to read provider-specific config
                  (API keys, URLs, etc.).

    Returns:
        The newly instantiated ``RoutingProvider``.

    Raises:
        ValueError: If *name* is not a recognised provider.
        NotImplementedError: If the provider exists in the registry but has
                             not been implemented yet.
    """
    global _active_provider
    # Temporarily override TRAFFIC_PROVIDER in a settings copy so the factory
    # picks up the correct provider without mutating the cached Settings object.
    overridden = settings.model_copy(update={"TRAFFIC_PROVIDER": name})
    new_provider = get_routing_provider(overridden)
    async with _lock:
        _active_provider = new_provider
    return new_provider


def get_active_provider(request: Request) -> RoutingProvider:
    """FastAPI dependency — returns the currently active ``RoutingProvider``.

    Reads from ``request.app.state.routing_provider`` so that the provider
    set during ``lifespan`` (or updated via the settings endpoint) is always
    authoritative.
    """
    return request.app.state.routing_provider


# Convenience type alias for use in route signatures.
ProviderDep = Annotated[RoutingProvider, Depends(get_active_provider)]
