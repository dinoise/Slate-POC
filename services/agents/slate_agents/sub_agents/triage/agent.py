"""Triage sub-agent — Phase 4 implementation.

Automatically classifies new incidents after POST /api/v1/incidents:
- Incident type classification (collision, theft, natural_disaster, etc.)
- Severity assessment (low, medium, high, critical)
- Optional: photo analysis via multimodal input

This is NOT a conversational agent — it runs as an automatic pipeline
triggered by slate-api after incident creation.
"""

from __future__ import annotations

# TODO (Phase 4): Import tools and implement full agent
# from .tools import classify_incident, assess_severity, analyze_incident_photo
from google.adk.agents import Agent

from ...core import settings

triage_agent = Agent(
    model=settings.ROOT_AGENT_MODEL,
    name="triage",
    instruction="""
Eres el agente de Triage de Slate — clasificador automático de siniestros.

Dado el contexto de un incidente recién reportado, debes:
1. Clasificar el tipo de siniestro (colisión, robo, desastre natural, incendio, etc.).
2. Evaluar la severidad (baja, media, alta, crítica) según descripción, ubicación y contexto.
3. Si hay imagen disponible, analízala para refinar la clasificación.
4. Retornar un objeto JSON con: incident_type, severity, confidence, reasoning.

Sé determinista y conciso — este es un pipeline automático, no una conversación.
""",
    # tools=[classify_incident, assess_severity],
)
