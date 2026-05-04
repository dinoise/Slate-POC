"""Field guide tools: external service coordination and field note logging."""

from __future__ import annotations

import httpx

from ....core.config import settings
from ....core.http_auth import get_api_headers
from ....core.logging import get_logger

logger = get_logger(__name__)

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
    logger.info(
        "request_emergency_service called | service=%s reason=%r",
        service,
        reason[:80] if reason else "",
    )

    if service not in _VALID_SERVICES:
        logger.warning(
            "request_emergency_service: invalid service=%r valid=%s", service, _VALID_SERVICES
        )
        return {
            "error": f"Servicio '{service}' no reconocido.",
            "valid_services": sorted(_VALID_SERVICES),
        }

    requested: list[dict] = tool_context.state.get("requested_services", [])
    already = any(r["service"] == service for r in requested)

    if not already:
        requested.append({"service": service, "reason": reason, "status": "solicitado"})
        tool_context.state["requested_services"] = requested
        logger.info(
            "request_emergency_service: registered service=%s | total_requested=%d",
            service,
            len(requested),
        )
    else:
        logger.debug("request_emergency_service: service=%s already requested", service)

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
    logger.debug("get_service_request_status called | total_requested=%d", len(requested))
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
    logger.info(
        "log_field_note called | assignment_id=%s note_len=%d",
        assignment_id,
        len(note) if note else 0,
    )

    if not assignment_id:
        logger.error(
            "log_field_note: assignment_id missing from session state. "
            "incident_id=%s agent_type=%s",
            tool_context.state.get("incident_id"),
            tool_context.state.get("agent_type"),
        )
        return {"error": "assignment_id not found in session state"}

    if not note or not note.strip():
        logger.warning("log_field_note: empty note rejected | assignment_id=%s", assignment_id)
        return {"error": "Note content cannot be empty"}

    url = f"{settings.SLATE_API_URL}/api/v1/assignments/{assignment_id}/notes"
    payload = {"content": note.strip(), "created_by_agent": True, "agent_type": "field_guide"}
    logger.debug("log_field_note: POST %s | payload_len=%d", url, len(note))

    try:
        headers = get_api_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        logger.info(
            "log_field_note: response status=%s assignment_id=%s",
            response.status_code,
            assignment_id,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "log_field_note: HTTP error %s | assignment_id=%s | body=%s",
            exc.response.status_code,
            assignment_id,
            exc.response.text[:200],
        )
        return {"error": f"API returned {exc.response.status_code}", "assignment_id": assignment_id}
    except httpx.TimeoutException:
        logger.error("log_field_note: timeout calling %s", url)
        return {"error": "Request timed out", "assignment_id": assignment_id}
    except Exception as exc:
        logger.exception("log_field_note: unexpected error | assignment_id=%s", assignment_id)
        return {"error": str(exc), "assignment_id": assignment_id}
