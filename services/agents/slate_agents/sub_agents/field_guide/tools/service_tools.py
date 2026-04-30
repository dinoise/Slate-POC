"""Field guide tools: external service coordination and field note logging."""

from __future__ import annotations

import httpx

from ....core.config import settings
from ....core.http_auth import get_api_headers

_VALID_SERVICES = {"ambulancia", "grua", "policia", "bomberos"}


def request_emergency_service(service: str, reason: str, tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Requests an external emergency service (simulated for POC).

    Records the request in the session state under 'requested_services' and
    returns a confirmation. Does NOT make a real external call — simulation only.

    Args:
        service: One of 'ambulancia', 'grua', 'policia', 'bomberos'.
        reason: Brief description of why the service is needed.

    Returns:
        dict with confirmation status and the list of all requested services.
    """
    service = service.lower().strip()
    if service not in _VALID_SERVICES:
        return {
            "error": f"Servicio '{service}' no reconocido.",
            "valid_services": sorted(_VALID_SERVICES),
        }

    requested: list[dict] = tool_context.state.get("requested_services", [])
    already = any(r["service"] == service for r in requested)

    if not already:
        requested.append({"service": service, "reason": reason, "status": "solicitado"})
        tool_context.state["requested_services"] = requested

    return {
        "confirmed": True,
        "service": service,
        "already_requested": already,
        "message": (
            f"{'Ya solicitado previamente' if already else 'Solicitud registrada'}: {service}."
        ),
        "all_requested_services": requested,
    }


def get_service_request_status(tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Returns the current status of all emergency service requests in this session.

    Reads the 'requested_services' list from session state — no API call needed.

    Returns:
        dict with the list of requested services and their statuses.
    """
    requested: list[dict] = tool_context.state.get("requested_services", [])
    return {
        "total": len(requested),
        "services": requested,
        "message": "No hay servicios solicitados en esta sesión." if not requested else None,
    }


async def log_field_note(note: str, tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Logs a field note for the current assignment via slate-api.

    Reads assignment_id from session state and POSTs the note to
    /api/v1/assignments/{id}/notes. Notes are persisted and visible to dispatchers.

    Args:
        note: The note content to log (max 2000 characters recommended).

    Returns:
        dict with the created note record, or an error dict on failure.
    """
    assignment_id = tool_context.state.get("assignment_id")
    if not assignment_id:
        return {"error": "assignment_id not found in session state"}

    if not note or not note.strip():
        return {"error": "Note content cannot be empty"}

    url = f"{settings.SLATE_API_URL}/api/v1/assignments/{assignment_id}/notes"
    payload = {"content": note.strip(), "created_by_agent": True, "agent_type": "field_guide"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=get_api_headers())
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"API returned {exc.response.status_code}", "assignment_id": assignment_id}
    except Exception as exc:
        return {"error": str(exc), "assignment_id": assignment_id}
