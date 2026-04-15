"""OSRM routing provider implementation."""

from __future__ import annotations

import logging

import httpx
import numpy as np

from ..base import Coord, RouteResult, RoutingProvider

logger = logging.getLogger(__name__)


class OSRMProvider(RoutingProvider):
    """Routing provider backed by a self-hosted OSRM instance.

    Inputs are expected to be pre-filtered by PostGIS (e.g. via the
    ``GET /adjusters/available/?radius_km=…`` endpoint), so no haversine
    pre-filtering or batching is performed here — a single HTTP call to
    ``/table`` or ``/route`` is sufficient.

    Args:
        base_url: Base URL of the OSRM HTTP server (e.g. ``http://localhost:5001``).
        timeout: HTTP timeout in seconds for routing requests.
        transport: Optional httpx transport — inject ``httpx.MockTransport`` in tests.
    """

    @property
    def provider_name(self) -> str:
        return "osrm"

    @property
    def supports_traffic(self) -> bool:
        return False

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        """Return a configured AsyncClient, optionally with an injected transport."""
        return httpx.AsyncClient(
            timeout=timeout or self._timeout,
            transport=self._transport,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def table(
        self,
        sources: list[Coord],
        destinations: list[Coord],
    ) -> np.ndarray:
        """Call ``/table/v1/driving`` and return a (n_sources × n_dest) matrix.

        OSRM returns ``null`` for unreachable pairs; these are converted to
        ``np.inf`` so OR-Tools treats them as infinitely expensive.

        Args:
            sources: List of (lat, lon) origin coordinates.
            destinations: List of (lat, lon) destination coordinates.

        Returns:
            Float array shaped (n_sources, n_destinations). Unreachable = np.inf.
        """
        coords = sources + destinations
        coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
        src_idx = ";".join(str(i) for i in range(len(sources)))
        dst_idx = ";".join(str(i) for i in range(len(sources), len(coords)))

        url = (
            f"{self._base_url}/table/v1/driving/{coord_str}"
            f"?sources={src_idx}&destinations={dst_idx}&annotations=duration"
        )

        async with self._client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        matrix = np.array(data["durations"], dtype=float)
        # OSRM encodes unreachable pairs as null → NaN in numpy; normalize to inf
        matrix[np.isnan(matrix)] = np.inf

        logger.debug(
            "OSRM table: %d sources × %d destinations, unreachable=%d",
            len(sources),
            len(destinations),
            np.isinf(matrix).sum(),
        )
        return matrix

    async def route(
        self,
        origin: Coord,
        destination: Coord,
    ) -> RouteResult:
        """Call ``/route/v1/driving`` and return the fastest route.

        Args:
            origin: (lat, lon) starting point.
            destination: (lat, lon) ending point.

        Returns:
            RouteResult with duration, distance, and encoded polyline.

        Raises:
            httpx.HTTPStatusError: If OSRM returns a non-2xx response.
            ValueError: If OSRM returns no routes.
        """
        olat, olon = origin
        dlat, dlon = destination
        url = (
            f"{self._base_url}/route/v1/driving"
            f"/{olon},{olat};{dlon},{dlat}"
            f"?overview=full&geometries=polyline"
        )

        async with self._client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned no routes: {data.get('code')}")

        best = data["routes"][0]
        return RouteResult(
            duration_s=best["duration"],
            distance_m=best["distance"],
            polyline=best["geometry"],
            provider=self.provider_name,
        )

    async def ping(self) -> bool:
        """Return True if the OSRM server is reachable and responding."""
        url = f"{self._base_url}/route/v1/driving/-99.1332,19.4326;-99.15,19.42?overview=false"
        try:
            async with self._client(timeout=3.0) as client:
                resp = await client.get(url)
                return resp.json().get("code") == "Ok"
        except Exception:
            return False
