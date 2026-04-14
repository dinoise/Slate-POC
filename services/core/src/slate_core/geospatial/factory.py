"""Factory for instantiating the configured RoutingProvider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import RoutingProvider
from .providers import GoogleRoutesProvider, OSRMProvider, ValhallaProvider

if TYPE_CHECKING:
    from slate_api.core.config import Settings

_SUPPORTED_PROVIDERS = ("osrm", "valhalla", "google")


def get_routing_provider(settings: Settings) -> RoutingProvider:
    """Return the RoutingProvider configured in *settings*.

    Args:
        settings: Application settings instance (from ``core/config.py``).

    Returns:
        A concrete ``RoutingProvider`` ready to use.

    Raises:
        ValueError: If ``TRAFFIC_PROVIDER`` is not a recognized value.
        NotImplementedError: If the provider is recognized but not yet implemented.
    """
    provider = settings.TRAFFIC_PROVIDER.lower().strip()

    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown TRAFFIC_PROVIDER={provider!r}. "
            f"Supported values: {', '.join(_SUPPORTED_PROVIDERS)}"
        )

    if provider == "osrm":
        return OSRMProvider(base_url=settings.OSRM_URL)

    if provider == "valhalla":
        return ValhallaProvider(base_url=settings.VALHALLA_URL)

    if provider == "google":
        return GoogleRoutesProvider(api_key=settings.GOOGLE_ROUTES_API_KEY)

    # Unreachable — kept for exhaustiveness
    raise ValueError(f"Unhandled provider: {provider!r}")  # pragma: no cover
