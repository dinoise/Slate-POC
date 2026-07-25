"""Slate root agent — entry point for ADK.

ADK discovers this module via `adk web` and `adk deploy agent_engine`.
It looks for an object named `agent` or `root_agent` (or `app` for App wrapper).

Architecture:
    root_agent (orchestrator)
    ├── field_guide_agent   — guides adjusters in the field (Phase 2)
    ├── coordinator_agent   — assists dispatchers with assignments (Phase 3)
    ├── triage_agent        — auto-classifies new incidents (Phase 4)
    └── analytics_agent     — conversational analytics for observatory (Phase 5)

Session initial_state is injected once at session creation by slate-api
(services/api/vertex_agents/session_manager.py) and persisted by ADK
throughout the conversation. Sub-agents read it via callback_context.state.

Context caching is enabled via App wrapper — reduces token costs 75–90%
for repeated system instructions across requests.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps import App
from google.genai import types

from .core import get_logger, settings
from .prompts import ROOT_AGENT_GLOBAL_INSTRUCTION, ROOT_AGENT_PROMPT
from .sub_agents import (
    field_guide_agent,
)

logger = get_logger(__name__)

# ── Root agent ────────────────────────────────────────────────────────────────

root_agent = Agent(
    model=settings.ROOT_AGENT_MODEL,
    name="slate_agents",
    instruction=ROOT_AGENT_PROMPT,
    global_instruction=ROOT_AGENT_GLOBAL_INSTRUCTION,
    sub_agents=[
        field_guide_agent,
        # analytics_agent,
        # coordinator_agent,
        # triage_agent,
    ],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.05,
        max_output_tokens=2048,
    ),
)

# ── App wrapper with context caching ─────────────────────────────────────────
# Exporting `app` instead of just `root_agent` enables Agent Engine's context
# caching: static system instructions are cached for 1h, cutting token costs
# by 75–90% on repeated requests.
#
# Requirements:
# - Gemini 2.0+ model
# - Minimum 2048 tokens in cached content

app = App(
    name="slate_agents",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=3600,  # 1 hour
        cache_intervals=10,
    ),
)
