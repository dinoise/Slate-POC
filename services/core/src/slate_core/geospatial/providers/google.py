"""Google Routes API v2 routing provider implementation."""
from __future__ import annotations

import logging

import httpx
import numpy as np

from ..base import Coord, RouteResult, RoutingProvider, TrafficSegment

logger = logging.getLogger(__name__)

_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
_ROUTE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Maximum origins × destinations allowed by the Google Routes API per request.
# With traffic enabled the limit drops to 100 elements (10×10); without traffic
# it is 625 (25×25).  We expose these as constants so callers can batch if needed.
MAX_ELEMENTS_NO_TRAFFIC = 625
MAX_ELEMENTS_WITH_TRAFFIC = 100


def _waypoint(lat: float, lon: float) -> dict:
    """Build a Google Routes API waypoint dict from (lat, lon)."""
    return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}


class GoogleRoutesProvider(RoutingProvider):
    """Routing provider backed by the Google Routes API v2.

    Uses ``computeRouteMatrix`` for travel-time matrices and
    ``computeRoutes`` for point-to-point routes.  Both endpoints support
    real-time traffic via ``routingPreference=TRAFFIC_AWARE``, which is
    why :py:attr:`supports_traffic` returns ``True``.

    Args:
        api_key: Google Cloud API key with the Routes API enabled.
        timeout: HTTP timeout in seconds (default 30 s).
        use_traffic: When ``True`` (default) uses ``TRAFFIC_AWARE`` routing
            preference so durations reflect current traffic conditions.
            Set to ``False`` to get static travel times (faster, cheaper).
        transport: Optional httpx transport — inject ``httpx.MockTransport``
            in tests to avoid real network calls.

    Note:
        The Routes API charges per element (origin × destination pair).
        ``table()`` sends a single POST for the entire matrix; ``route()``
        sends a single POST for one pair.
    """

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def supports_traffic(self) -> bool:
        return True

    def __init__(
        self,
        api_key: str,
        timeout: float = 30.0,
        use_traffic: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._use_traffic = use_traffic
        self._transport = transport

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        """Return a configured AsyncClient with Google auth headers."""
        return httpx.AsyncClient(
            timeout=timeout or self._timeout,
            headers={"X-Goog-Api-Key": self._api_key},
            transport=self._transport,
        )

    @property
    def _routing_preference(self) -> str:
        """Return the routingPreference value for matrix/route requests."""
        return "TRAFFIC_AWARE" if self._use_traffic else "DEFAULT_BEST_GUESS"

    # ── Public API ─────────────────────────────────────────────────────────────

    async def table(
        self,
        sources: list[Coord],
        destinations: list[Coord],
    ) -> np.ndarray:
        """Call ``computeRouteMatrix`` and return a (n_sources × n_dest) matrix.

        Google returns a JSON array where each element represents one
        (origin, destination) pair and carries ``originIndex``, ``destinationIndex``,
        ``duration`` (protobuf string e.g. ``"120s"``), and ``condition``.
        Elements with ``ROUTE_NOT_FOUND`` or missing ``duration`` are filled
        with ``np.inf``.

        The field mask requests only the fields needed to minimise
        response size and billing.

        Args:
            sources: List of (lat, lon) origin coordinates.
            destinations: List of (lat, lon) destination coordinates.

        Returns:
            Float array shaped (n_sources, n_destinations). Unreachable = np.inf.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
        """
        body = {
            "origins": [
                {"waypoint": _waypoint(lat, lon)} for lat, lon in sources
            ],
            "destinations": [
                {"waypoint": _waypoint(lat, lon)} for lat, lon in destinations
            ],
            "travelMode": "DRIVE",
            "routingPreference": self._routing_preference,
        }
        field_mask = "originIndex,destinationIndex,duration,status,condition"

        n_src = len(sources)
        n_dst = len(destinations)
        matrix = np.full((n_src, n_dst), np.inf, dtype=float)

        logger.debug(f"Sources: {sources}")
        logger.debug(f"Destinations: {destinations}")

        async with self._client() as client:
            resp = await client.post(
                _MATRIX_URL,
                json=body,
                headers={"X-Goog-FieldMask": field_mask},
            )
            resp.raise_for_status()

            # The API returns a JSON array of route elements, each spanning
            # multiple lines.  Parse the full body at once — not line by line.
            elements: list[dict] = resp.json()

            for element in elements:
                if element.get("condition") == "ROUTE_NOT_FOUND":
                    continue  # leave as np.inf

                duration_str: str | None = element.get("duration")
                if duration_str is None:
                    continue

                # Duration is a protobuf Duration string: "123s" or "1.5s"
                try:
                    duration_s = float(duration_str.rstrip("s"))
                except ValueError:
                    continue

                i = element.get("originIndex", -1)
                j = element.get("destinationIndex", -1)
                if 0 <= i < n_src and 0 <= j < n_dst:
                    matrix[i, j] = duration_s

        unreachable = int(np.isinf(matrix).sum())
        
        if unreachable > 0:
            # Encontrar los pares que quedaron inf
            failed_pairs = list(zip(*np.where(np.isinf(matrix))))
            logger.warning(f"Unreachable pairs: {failed_pairs}")

        logger.debug(
            "Google table: %d sources × %d destinations, unreachable=%d, traffic=%s",
            n_src,
            n_dst,
            unreachable,
            self._use_traffic,
        )
        return matrix

    async def route(
        self,
        origin: Coord,
        destination: Coord,
    ) -> RouteResult:
        """Call ``computeRoutes`` and return the fastest route.

        Args:
            origin: (lat, lon) starting point.
            destination: (lat, lon) ending point.

        Returns:
            RouteResult with duration, distance, and encoded polyline.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
            ValueError: If the API returns no routes.
        """
        olat, olon = origin
        dlat, dlon = destination

        body = {
            "origin": {"location": {"latLng": {"latitude": olat, "longitude": olon}}},
            "destination": {"location": {"latLng": {"latitude": dlat, "longitude": dlon}}},
            "travelMode": "DRIVE",
            "routingPreference": self._routing_preference,
            "computeAlternativeRoutes": False,
            "polylineQuality": "HIGH_QUALITY",
            "polylineEncoding": "ENCODED_POLYLINE",
            # Request per-segment traffic when traffic is enabled
            **({"extraComputations": ["TRAFFIC_ON_POLYLINE"]} if self._use_traffic else {}),
        }
        # legs.polyline holds the per-leg encoded path;
        # legs.travelAdvisory holds speedReadingIntervals when TRAFFIC_ON_POLYLINE is set.
        field_mask = (
            "routes.duration,routes.distanceMeters,"
            "routes.legs.polyline.encodedPolyline,"
            "routes.legs.travelAdvisory.speedReadingIntervals"
        )

        async with self._client() as client:
            resp = await client.post(
                _ROUTE_URL,
                json=body,
                headers={"X-Goog-FieldMask": field_mask},
            )
            resp.raise_for_status()
            data = resp.json()

        routes = data.get("routes") or []
        if not routes:
            raise ValueError(
                f"Google Routes returned no routes for "
                f"({olat},{olon}) → ({dlat},{dlon}): {data}"
            )

        best = routes[0]
        duration_str: str = best.get("duration", "0s")
        try:
            duration_s = float(duration_str.rstrip("s"))
        except ValueError:
            duration_s = 0.0

        # Assemble polyline and traffic segments from the first (and only) leg.
        legs = best.get("legs") or []
        polyline = ""
        traffic_segments: list[TrafficSegment] = []

        if legs:
            leg = legs[0]
            polyline = leg.get("polyline", {}).get("encodedPolyline", "")
            for interval in leg.get("travelAdvisory", {}).get("speedReadingIntervals", []):
                speed = interval.get("speed", "NORMAL")
                if speed not in ("NORMAL", "SLOW", "TRAFFIC_JAM"):
                    speed = "NORMAL"
                traffic_segments.append(TrafficSegment(
                    start_index=interval.get("startPolylinePointIndex", 0),
                    end_index=interval.get("endPolylinePointIndex", 0),
                    speed=speed,
                ))

        return RouteResult(
            duration_s=duration_s,
            distance_m=float(best.get("distanceMeters", 0)),
            polyline=polyline,
            provider=self.provider_name,
            traffic_segments=traffic_segments,
        )

    async def ping(self) -> bool:
        """Return True if the Google Routes API key is valid and the API is reachable.

        Sends a minimal ``computeRoutes`` request for two fixed points in CDMX.
        Returns ``False`` on any error (network, 401 invalid key, etc.).
        """
        try:
            result = await self.route(
                origin=(19.4326, -99.1332),
                destination=(19.42, -99.15),
            )
            return result.duration_s > 0
        except Exception:
            return False
