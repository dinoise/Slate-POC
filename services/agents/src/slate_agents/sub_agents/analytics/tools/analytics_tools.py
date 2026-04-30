"""Analytics sub-agent tools: operational metrics and real-time status queries."""

from __future__ import annotations

import httpx

from ....core.config import settings
from ....core.http_auth import get_api_headers


async def get_assignment_metrics(window_hours: int = 8) -> dict:
    """Fetches aggregated assignment metrics from slate-api for the given time window.

    Returns counts by status, resolution time statistics, and volume indicators
    for the requested window. Use this to answer questions about operational
    performance, backlog, and throughput.

    Args:
        window_hours: Hours to look back for volume and resolution stats (1–168).
                      Defaults to 8 (one shift). Use 24 for daily, 168 for weekly.

    Returns:
        dict with:
            - total_active: total assignments currently in active statuses
            - by_status: count per status (assigned, accepted, en_route, etc.)
            - avg_resolution_seconds: mean time to complete (None if no data)
            - median_resolution_seconds: p50 resolution time (None if no data)
            - window_hours: the requested window
            - completed_in_window: assignments completed in window
            - created_in_window: assignments created in window
    """
    window_hours = max(1, min(168, window_hours))
    url = f"{settings.SLATE_API_URL}/api/v1/assignments/metrics"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url, params={"window_hours": window_hours}, headers=get_api_headers()
            )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


async def get_active_assignments(status_filter: str | None = None) -> dict:
    """Fetches the list of current active assignments, optionally filtered by status.

    Use this when you need details about specific assignments in progress —
    not just counts. For aggregate metrics prefer get_assignment_metrics.

    Args:
        status_filter: Optional status to filter by. Valid values:
            'assigned', 'accepted', 'en_route', 'arrived', 'in_progress'.
            If None, returns all active assignments (up to 200).

    Returns:
        dict with:
            - total: number of assignments returned
            - items: list of assignment records
            - status_filter: the filter applied (or null)
    """
    url = f"{settings.SLATE_API_URL}/api/v1/assignments/"
    params: dict = {"limit": 200}
    if status_filter:
        params["status"] = status_filter

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=get_api_headers())
        response.raise_for_status()
        data = response.json()
        return {
            "total": data.get("total", 0),
            "items": data.get("items", []),
            "status_filter": status_filter,
        }
    except httpx.HTTPStatusError as exc:
        return {"error": f"API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


async def get_adjuster_availability() -> dict:
    """Fetches current adjuster availability — total count and available count.

    Use this to answer questions about workforce capacity: how many adjusters
    are in the system, how many are free to take new assignments, and how many
    are currently occupied.

    Returns:
        dict with:
            - total_adjusters: total adjusters in the system
            - available: adjusters with status 'available'
            - occupied: adjusters currently assigned
            - adjusters: list of adjuster records with name and status
    """
    url = f"{settings.SLATE_API_URL}/api/v1/adjusters/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params={"limit": 500}, headers=get_api_headers())
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        available = [a for a in items if a.get("status") == "available"]
        return {
            "total_adjusters": data.get("total", len(items)),
            "available": len(available),
            "occupied": len(items) - len(available),
            "adjusters": items,
        }
    except httpx.HTTPStatusError as exc:
        return {"error": f"API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


async def get_active_incidents() -> dict:
    """Fetches currently active (open) incidents from slate-api.

    Use this to understand the current incident load: how many open incidents
    exist, their types, and whether they have assignments.

    Returns:
        dict with:
            - total: total active incidents
            - items: list of incident records (id, type, status, description, location)
    """
    url = f"{settings.SLATE_API_URL}/api/v1/incidents/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url, params={"status": "active", "limit": 200}, headers=get_api_headers()
            )
        response.raise_for_status()
        data = response.json()
        return {
            "total": data.get("total", 0),
            "items": data.get("items", []),
        }
    except httpx.HTTPStatusError as exc:
        return {"error": f"API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}
