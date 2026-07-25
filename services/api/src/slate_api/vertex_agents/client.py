"""
Vertex AI Agent Engine client.

Adapted from mk-repo-agent-platform/backend/app/vertex_agents/client.py.
ModelArmorService is omitted for this POC.
"""

from collections.abc import AsyncGenerator
from threading import Lock
from typing import Any

import vertexai
from vertexai.agent_engines import AgentEngine

from ..core.logging import get_logger

logger = get_logger(__name__)


# ── Singleton client pool ─────────────────────────────────────────────────────


class _VertexClientPool:
    """Thread-safe pool that reuses vertexai.Client instances by project/location."""

    _instance: "_VertexClientPool | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "_VertexClientPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._clients: dict[str, vertexai.Client] = {}
                    cls._instance._client_lock = Lock()
        return cls._instance

    def get(self, project_id: str, location: str) -> vertexai.Client:
        key = f"{project_id}:{location}"
        if key not in self._clients:
            with self._client_lock:
                if key not in self._clients:
                    logger.info("Creating Vertex AI client for %s", key)
                    self._clients[key] = vertexai.Client(project=project_id, location=location)
        return self._clients[key]


_pool = _VertexClientPool()


# ── Main client ───────────────────────────────────────────────────────────────


class VertexAgentClient:
    """
    Async client for a deployed Vertex AI Agent Engine (ReasoningEngine).

    Provides session management and streaming message processing.
    One instance per Agent Engine resource ID.
    """

    def __init__(self, project_id: str, location: str, resource_id: str) -> None:
        self.project_id = project_id
        self.location = location
        self.resource_id = resource_id

        client = _pool.get(project_id, location)
        agent_name = f"projects/{project_id}/locations/{location}/reasoningEngines/{resource_id}"
        self.adk_app: AgentEngine = client.agent_engines.get(name=agent_name)
        logger.info("VertexAgentClient ready: %s", resource_id)

    # ── Session management ────────────────────────────────────────────────────

    async def create_session(
        self, user_id: str, initial_state: dict[str, Any] | None = None
    ) -> tuple[str, Any]:
        params: dict[str, Any] = {"user_id": user_id}
        if initial_state:
            params["state"] = initial_state
        session = await self.adk_app.async_create_session(**params)
        session_id = session.get("id") if isinstance(session, dict) else session.id
        logger.debug("Created session %s for user %s", session_id, user_id)
        return (session_id, session)

    async def get_session(self, user_id: str, session_id: str) -> Any | None:
        try:
            return await self.adk_app.async_get_session(user_id=user_id, session_id=session_id)
        except Exception as exc:
            logger.warning("Failed to get session %s: %s", session_id, exc)
            return None

    async def session_exists(self, user_id: str, session_id: str) -> bool:
        return await self.get_session(user_id, session_id) is not None

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        try:
            await self.adk_app.async_delete_session(user_id=user_id, session_id=session_id)
            logger.debug("Deleted session %s", session_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete session %s: %s", session_id, exc)
            return False

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream agent responses token by token.

        Yields dicts: {"type": "text_chunk"|"error", "content": str}
        """
        try:
            async for event in self.adk_app.async_stream_query(
                user_id=user_id, session_id=session_id, message=message
            ):
                chunk = self._extract_chunk(event)
                if chunk:
                    yield chunk
        except Exception as exc:
            logger.error("Stream error: %s", exc)
            yield {"type": "error", "content": str(exc)}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_chunk(self, event: Any) -> dict[str, Any] | None:
        try:
            content = (
                event.content
                if hasattr(event, "content")
                else (event.get("content", {}) if isinstance(event, dict) else None)
            )
            if not content:
                return None

            parts = content.get("parts", []) if isinstance(content, dict) else []
            role = content.get("role", "") if isinstance(content, dict) else ""

            for part in parts:
                if "text" in part:
                    return {"type": "text_chunk", "content": part["text"], "role": role}
                # function_call / function_response events are intentionally skipped —
                # the agent handles tool execution internally before streaming final text
            return None
        except Exception as exc:
            logger.debug("Could not extract chunk from event: %s", exc)
            return None
