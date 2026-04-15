"""Base abstractions for routing providers."""

from abc import ABC, abstractmethod
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

# Shared type alias: (latitude, longitude)
Coord = tuple[float, float]

TrafficSpeed = Literal["NORMAL", "SLOW", "TRAFFIC_JAM"]


class TrafficSegment(BaseModel):
    """One traffic-coloured segment of a route polyline.

    ``start_index`` and ``end_index`` are inclusive/exclusive indices into the
    **decoded** polyline point list.  Slice ``points[start_index:end_index+1]``
    to get the coordinates for this segment.

    Providers that do not support per-segment traffic (e.g. OSRM) return an
    empty ``traffic_segments`` list in ``RouteResult`` — the frontend then
    renders the route in a single colour.
    """

    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., ge=0)
    speed: TrafficSpeed


class RouteResult(BaseModel):
    """Result of a single origin → destination route query."""

    duration_s: float = Field(..., ge=0, description="Travel time in seconds")
    distance_m: float = Field(..., ge=0, description="Distance in meters")
    polyline: str = Field(..., description="Precision-5 encoded polyline")
    provider: str = Field(..., description="Provider that computed this route")
    traffic_segments: list[TrafficSegment] = Field(
        default_factory=list,
        description=(
            "Per-segment traffic conditions mapped onto the decoded polyline. "
            "Empty when the provider does not support traffic data."
        ),
    )


class RoutingProvider(ABC):
    """Abstract base class for routing providers.

    Implementations must provide travel-time matrices (for OR-Tools) and
    point-to-point routes (for the map UI). Each provider encapsulates its
    own HTTP client, authentication, and encoding details.

    Supported providers: osrm | valhalla | google
    """

    @abstractmethod
    async def table(
        self,
        sources: list[Coord],
        destinations: list[Coord],
    ) -> np.ndarray:
        """Return an (n_sources × n_destinations) travel-time matrix in seconds.

        Unreachable pairs must be represented as ``np.inf`` (not NaN),
        so OR-Tools can safely treat them as infinitely expensive.

        Args:
            sources: List of (lat, lon) origin coordinates.
            destinations: List of (lat, lon) destination coordinates.

        Returns:
            Float array shaped (n_sources, n_destinations).
        """

    @abstractmethod
    async def route(
        self,
        origin: Coord,
        destination: Coord,
    ) -> RouteResult:
        """Return the fastest route between two points.

        Args:
            origin: (lat, lon) of the starting point.
            destination: (lat, lon) of the ending point.

        Returns:
            RouteResult with duration, distance, and encoded polyline.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g. ``"osrm"``, ``"valhalla"``)."""

    @property
    @abstractmethod
    def supports_traffic(self) -> bool:
        """True if this provider returns real-time or historically traffic-aware durations.

        Used by the frontend to show or hide traffic-related UI indicators.
        OSRM (static graph) → False. Valhalla predicted_traffic / Google Routes → True.
        """

    @abstractmethod
    async def ping(self) -> bool:
        """Return True if the provider is reachable and healthy."""
