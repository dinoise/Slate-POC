"""
Session manager for Vertex AI Agent Engine.

Adapted from mk-repo-agent-platform/backend/app/vertex_agents/session_manager.py.
"""

from datetime import UTC, datetime
from typing import Any

from google.adk.sessions import VertexAiSessionService
from google.adk.sessions.session import Session

from ..core.logging import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Wraps VertexAiSessionService for cloud-based session persistence.

    Sessions are stored in Vertex AI — no local DB required.
    """

    def __init__(self, project_id: str, location: str, app_name: str) -> None:
        self.project_id = project_id
        self.location = location
        self.app_name = app_name
        self._svc = VertexAiSessionService(
            project_id=project_id, location=location, app_name=app_name
        )
        logger.info("SessionManager ready for app: %s", app_name)

    async def create_session(
        self, user_id: str, initial_state: dict[str, Any] | None = None
    ) -> tuple[str, Session]:
        state = {
            "conversation_metadata": {
                "user_id": user_id,
                "created_at": datetime.now(UTC).isoformat(),
            },
            **(initial_state or {}),
        }
        session = await self._svc.create_session(user_id=user_id, state=state)
        logger.debug("Created session %s for user %s", session.id, user_id)
        return (session.id, session)

    async def get_session(self, user_id: str, session_id: str) -> Session | None:
        try:
            return await self._svc.get_session(user_id=user_id, session_id=session_id)
        except Exception as exc:
            logger.warning("Failed to get session %s: %s", session_id, exc)
            return None

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        try:
            await self._svc.delete_session(user_id=user_id, session_id=session_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete session %s: %s", session_id, exc)
            return False

    async def list_sessions(self, user_id: str) -> list[Session]:
        try:
            response = await self._svc.list_sessions(user_id=user_id)
            return list(response.sessions) if response.sessions else []
        except Exception as exc:
            logger.error("Failed to list sessions for user %s: %s", user_id, exc)
            return []
