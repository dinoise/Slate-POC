"""Shared tools available to all sub-agents."""

from __future__ import annotations

from datetime import UTC, datetime

from ..core.logging import get_logger

logger = get_logger(__name__)


def get_current_datetime() -> dict[str, str]:
    """Returns the current date and time in ISO 8601 format (UTC).

    Use this tool when you need to know the current date or time to answer
    questions about schedules, deadlines, or time-sensitive information.

    Returns:
        dict with keys:
            - iso: ISO 8601 string (e.g. "2026-04-26T15:30:00+00:00")
            - date: date only (e.g. "2026-04-26")
            - time: time only HH:MM (e.g. "15:30")
            - weekday: Spanish weekday name (e.g. "Sábado")
    """
    now = datetime.now(tz=UTC)
    weekdays_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    result = {
        "iso": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M"),
        "weekday": weekdays_es[now.weekday()],
    }
    logger.debug("get_current_datetime: %s", result["iso"])
    return result


def get_session_context(tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Returns the session context injected at session creation (initial_state).

    Sub-agents can call this to retrieve the context injected when the session
    was created — e.g. the assignment details for a field_guide session, or
    the current shift context for the coordinator.

    Returns:
        dict with all keys set in initial_state at session creation.
    """
    state = dict(tool_context.state)
    logger.info(
        "get_session_context called | keys=%s | assignment_id=%s incident_id=%s agent_type=%s",
        list(state.keys()),
        state.get("assignment_id"),
        state.get("incident_id"),
        state.get("agent_type"),
    )
    return state
