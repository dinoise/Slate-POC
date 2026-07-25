"""
Agent orchestration service.

Manages Vertex AI Agent Engine sessions and streaming for the two active
sub-agents: field_guide (adjuster app) and analytics (admin observatory).

The service is intentionally thin: it delegates session persistence to
SessionManager and streaming to VertexAgentClient. The only business logic
here is mapping agent_type → initial_state and enforcing that AGENT_ENGINE_ID
is configured before attempting any Vertex AI call.
"""

from collections.abc import AsyncGenerator
from typing import Any, Literal

from ..core.config import settings
from ..core.exceptions import AppException, NotFoundError
from ..core.logging import get_logger
from ..vertex_agents.client import VertexAgentClient
from ..vertex_agents.session_manager import SessionManager

logger = get_logger(__name__)

AgentType = Literal["field_guide", "analytics"]

_NOT_CONFIGURED_MSG = (
    "Agent Engine is not configured. Set VERTEX_PROJECT and AGENT_ENGINE_ID in the environment."
)


class AgentNotConfiguredError(AppException):
    def __init__(self) -> None:
        super().__init__(status_code=503, message=_NOT_CONFIGURED_MSG)


class AgentService:
    """
    Orchestrates AI agent sessions and streaming.

    One instance per request (FastAPI dependency injection).
    The underlying VertexAgentClient reuses a pooled vertexai.Client
    connection — no new TCP handshake per request.
    """

    def __init__(self) -> None:
        if not settings.agent_engine_configured:
            # Raise lazily — let the route return 503 rather than crashing startup
            self._configured = False
            return

        self._configured = True
        self._client = VertexAgentClient(
            project_id=settings.VERTEX_PROJECT,
            location=settings.VERTEX_LOCATION,
            resource_id=settings.AGENT_ENGINE_ID,
        )
        self._sessions = SessionManager(
            project_id=settings.VERTEX_PROJECT,
            location=settings.VERTEX_LOCATION,
            app_name=settings.AGENT_ENGINE_ID,
        )

    def _require_configured(self) -> None:
        if not self._configured:
            raise AgentNotConfiguredError()

    # ── Session lifecycle ──────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: str,
        agent_type: AgentType,
        context: dict[str, Any],
    ) -> str:
        """
        Create an Agent Engine session with the appropriate initial_state.

        The initial_state is injected once at session creation and persisted
        by ADK throughout the conversation — sub-agents read it via
        tool_context.state without re-injecting it on every turn.
        """
        self._require_configured()

        initial_state = self._build_initial_state(agent_type, context)
        session_id, _ = await self._sessions.create_session(
            user_id=user_id, initial_state=initial_state
        )
        logger.info("Created %s session %s for user %s", agent_type, session_id, user_id)
        return session_id

    async def delete_session(self, user_id: str, session_id: str) -> None:
        self._require_configured()
        deleted = await self._sessions.delete_session(user_id=user_id, session_id=session_id)
        if not deleted:
            raise NotFoundError(f"Session {session_id} not found")

    # ── Streaming ──────────────────────────────────────────────────────────────

    async def stream_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Stream SSE-formatted chunks from the agent.

        Each chunk is a complete `data: ...\n\n` SSE line so the route can
        forward them directly into a StreamingResponse without transformation.
        Yields a terminal `data: [DONE]\n\n` when the agent finishes.
        """
        self._require_configured()

        if not await self._client.session_exists(user_id=user_id, session_id=session_id):
            raise NotFoundError(f"Session {session_id} not found")

        async for event in self._client.stream(
            user_id=user_id, session_id=session_id, message=message
        ):
            if event.get("type") == "text_chunk":
                # Escape newlines so the SSE line stays single-line
                content = event["content"].replace("\n", "\\n")
                yield f"data: {content}\n\n"
            elif event.get("type") == "error":
                yield f"data: [ERROR] {event['content']}\n\n"
                return

        yield "data: [DONE]\n\n"

    # ── Initial state builders ─────────────────────────────────────────────────

    def _build_initial_state(
        self, agent_type: AgentType, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Map frontend context payload → ADK initial_state dict.

        field_guide expects: assignment_id, incident_id, incident_type,
                             incident_description, adjuster_id
        analytics expects:  dispatcher_id, active_assignment_count (optional hints)
        """
        base: dict[str, Any] = {"agent_type": agent_type}

        if agent_type == "field_guide":
            base.update(
                {
                    "assignment_id": context.get("assignment_id"),
                    "incident_id": context.get("incident_id"),
                    "incident_type": context.get("incident_type"),
                    "incident_description": context.get("incident_description", ""),
                    "adjuster_id": context.get("adjuster_id"),
                }
            )
        elif agent_type == "analytics":
            base.update(
                {
                    "dispatcher_id": context.get("dispatcher_id"),
                    "active_assignment_count": context.get("active_assignment_count", 0),
                }
            )

        return base
