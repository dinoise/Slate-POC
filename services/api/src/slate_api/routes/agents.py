"""AI agent routes — session management and SSE streaming."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.auth import CurrentUser
from ..services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service() -> AgentService:
    return AgentService()


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


# ── Request / response schemas ────────────────────────────────────────────────


class SessionCreateRequest(BaseModel):
    agent_type: Literal["field_guide", "analytics"]
    context: dict[str, Any] = {}


class SessionCreateResponse(BaseModel):
    session_id: str


class StreamRequest(BaseModel):
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent session with initial context",
)
async def create_session(
    body: SessionCreateRequest,
    service: AgentServiceDep,
    current_user: CurrentUser,
) -> SessionCreateResponse:
    """
    Create a new Agent Engine session.

    The `context` payload is injected as initial_state once and persisted
    for the entire conversation — no need to resend it on each turn.

    - **field_guide**: pass assignment_id, incident_id, incident_type, adjuster_id
    - **analytics**: pass dispatcher_id, active_assignment_count (optional hints)
    """
    session_id = await service.create_session(
        user_id=str(current_user.id),
        agent_type=body.agent_type,
        context=body.context,
    )
    return SessionCreateResponse(session_id=session_id)


@router.post(
    "/sessions/{session_id}/stream",
    summary="Send a message and stream the agent response (SSE)",
)
async def stream_message(
    session_id: str,
    body: StreamRequest,
    service: AgentServiceDep,
    current_user: CurrentUser,
) -> StreamingResponse:
    """
    Send a message and receive a Server-Sent Events stream.

    Each event is `data: <text_chunk>\\n\\n`.
    The stream ends with `data: [DONE]\\n\\n`.
    On error: `data: [ERROR] <message>\\n\\n`.

    The frontend should consume this with `response.body.getReader()` (Fetch API),
    NOT with `EventSource` — EventSource only supports GET and cannot send a body.
    """
    return StreamingResponse(
        service.stream_message(
            user_id=str(current_user.id),
            session_id=session_id,
            message=body.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent session",
)
async def delete_session(
    session_id: str,
    service: AgentServiceDep,
    current_user: CurrentUser,
) -> None:
    """Delete an Agent Engine session and free its resources."""
    await service.delete_session(user_id=str(current_user.id), session_id=session_id)
