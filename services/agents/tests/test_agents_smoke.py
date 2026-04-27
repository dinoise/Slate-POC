"""Smoke tests — verify agents are importable and properly structured."""

from __future__ import annotations


def test_root_agent_importable() -> None:
    """Root agent module must be importable without crashing."""
    from slate_agents.agent import app, root_agent

    assert root_agent is not None
    assert app is not None
    assert root_agent.name == "slate_root"


def test_sub_agents_registered() -> None:
    """All 4 sub-agents must be registered under root_agent."""
    from slate_agents.agent import root_agent

    sub_agent_names = {a.name for a in root_agent.sub_agents}
    assert "field_guide" in sub_agent_names
    assert "coordinator" in sub_agent_names
    assert "triage" in sub_agent_names
    assert "analytics" in sub_agent_names


def test_settings_load() -> None:
    """Settings must load without errors (uses defaults if no .env)."""
    from slate_agents.core import settings

    assert settings.ROOT_AGENT_MODEL  # has a default
    assert isinstance(settings.is_local, bool)
