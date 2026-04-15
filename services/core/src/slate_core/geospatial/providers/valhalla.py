"""Valhalla routing provider implementation."""

from __future__ import annotations

import logging

import httpx
import numpy as np

from ..base import Coord, RouteResult, RoutingProvider

logger = logging.getLogger(__name__)

_ROUTE_URL = "/route"
_MATRIX_URL = "/sources_to_targets"

# Valhalla encodes polylines at precision 6 (scale factor 1e6).
# We re-encode to precision 5 so all providers share the same wire format.
_VALHALLA_PRECISION = 6
_OUTPUT_PRECISION = 5


def _decode_polyline(encoded: str, precision: int) -> list[tuple[float, float]]:
    """Decode an encoded polyline string to a list of (lat, lon) tuples."""
    scale = 10**precision
    coords: list[tuple[float, float]] = []
    index = lat = lng = 0
    while index < len(encoded):
        for is_lng in (False, True):
            result = shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 32:
                    break
            value = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += value
            else:
                lat += value
        coords.append((lat / scale, lng / scale))
    return coords


def _encode_polyline(coords: list[tuple[float, float]], precision: int) -> str:
    """Encode a list of (lat, lon) tuples to a polyline string."""
    scale = 10**precision
    output: list[str] = []
    prev_lat = prev_lng = 0
    for lat, lng in coords:
        for value, prev in [(round(lat * scale), prev_lat), (round(lng * scale), prev_lng)]:
            delta = value - prev
            delta = ~(delta << 1) if delta < 0 else delta << 1
            while delta >= 0x20:
                output.append(chr((0x20 | (delta & 0x1F)) + 63))
                delta >>= 5
            output.append(chr(delta + 63))
        prev_lat = round(lat * scale)
        prev_lng = round(lng * scale)
    return "".join(output)


def _transcode_polyline(encoded: str) -> str:
    """Re-encode a precision-6 Valhalla polyline as precision-5."""
    coords = _decode_polyline(encoded, _VALHALLA_PRECISION)
    return _encode_polyline(coords, _OUTPUT_PRECISION)


class ValhallaProvider(RoutingProvider):
    """Routing provider backed by a self-hosted Valhalla instance.

    Uses ``/sources_to_targets`` for travel-time matrices and ``/route``
    for point-to-point routes.  Both endpoints use OSM-based speed estimates
    (maxspeed tags, road type) — no real-time traffic feed required.

    Args:
        base_url: Base URL of the Valhalla HTTP server (e.g. ``http://localhost:8002``).
        timeout: HTTP timeout in seconds (default 30 s).
        costing: Valhalla costing model (default ``"auto"`` for car routing).
        transport: Optional httpx transport — inject ``httpx.MockTransport`` in tests.
    """

    @property
    def provider_name(self) -> str:
        return "valhalla"

    @property
    def supports_traffic(self) -> bool:
        return False

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        costing: str = "auto",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._costing = costing
        self._transport = transport

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
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
        """Call ``/sources_to_targets`` and return a (n_sources × n_dest) matrix.

        Valhalla returns ``null`` for unreachable pairs; these are converted to
        ``np.inf`` so OR-Tools treats them as infinitely expensive.

        Args:
            sources: List of (lat, lon) origin coordinates.
            destinations: List of (lat, lon) destination coordinates.

        Returns:
            Float array shaped (n_sources, n_destinations). Unreachable = np.inf.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
        """
        body = {
            "sources": [{"lat": lat, "lon": lon} for lat, lon in sources],
            "targets": [{"lat": lat, "lon": lon} for lat, lon in destinations],
            "costing": self._costing,
        }

        n_src = len(sources)
        n_dst = len(destinations)
        matrix = np.full((n_src, n_dst), np.inf, dtype=float)

        async with self._client() as client:
            resp = await client.post(f"{self._base_url}{_MATRIX_URL}", json=body)
            resp.raise_for_status()
            data = resp.json()

        # sources_to_targets is a list of rows (one per source),
        # each row is a list of {time, distance, from_index, to_index} dicts.
        # time is in seconds; null means unreachable.
        for row in data.get("sources_to_targets", []):
            for cell in row:
                i = cell.get("from_index", -1)
                j = cell.get("to_index", -1)
                t = cell.get("time")
                if t is not None and 0 <= i < n_src and 0 <= j < n_dst:
                    matrix[i, j] = float(t)

        unreachable = int(np.isinf(matrix).sum())
        logger.debug(
            "Valhalla table: %d sources × %d destinations, unreachable=%d",
            n_src,
            n_dst,
            unreachable,
        )
        return matrix

    async def route(
        self,
        origin: Coord,
        destination: Coord,
    ) -> RouteResult:
        """Call ``/route`` and return the fastest route.

        Valhalla encodes polylines at precision 6; this method re-encodes to
        precision 5 so the response is compatible with the frontend decoder and
        the rest of the provider interface.

        Args:
            origin: (lat, lon) starting point.
            destination: (lat, lon) ending point.

        Returns:
            RouteResult with duration, distance, and precision-5 encoded polyline.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
            ValueError: If Valhalla returns no routes.
        """
        olat, olon = origin
        dlat, dlon = destination

        body = {
            "locations": [
                {"lat": olat, "lon": olon},
                {"lat": dlat, "lon": dlon},
            ],
            "costing": self._costing,
            "units": "kilometers",
        }

        async with self._client() as client:
            resp = await client.post(f"{self._base_url}{_ROUTE_URL}", json=body)
            resp.raise_for_status()
            data = resp.json()

        trip = data.get("trip") or {}
        legs = trip.get("legs") or []
        if not legs:
            raise ValueError(
                f"Valhalla returned no route for ({olat},{olon}) → ({dlat},{dlon}): {data}"
            )

        leg = legs[0]
        summary = trip.get("summary", {})
        duration_s = float(summary.get("time", 0))
        # Valhalla reports distance in km (units="kilometers")
        distance_m = float(summary.get("length", 0)) * 1000

        # Re-encode precision-6 → precision-5 for a uniform wire format
        raw_shape = leg.get("shape", "")
        polyline = _transcode_polyline(raw_shape) if raw_shape else ""

        return RouteResult(
            duration_s=duration_s,
            distance_m=distance_m,
            polyline=polyline,
            provider=self.provider_name,
        )

    async def ping(self) -> bool:
        """Return True if the Valhalla server is reachable and responding."""
        try:
            result = await self.route(
                origin=(19.4326, -99.1332),
                destination=(19.42, -99.15),
            )
            return result.duration_s > 0
        except Exception:
            return False
