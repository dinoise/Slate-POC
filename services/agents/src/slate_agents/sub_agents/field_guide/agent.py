"""Field Guide sub-agent — Phase 2 implementation.

Assists adjusters in the field with:
- Step-by-step procedures by incident type
- Similar incident lookups
- Note logging (POST /api/v1/assignments/{id}/notes)
- Supervisor escalation
- External service coordination (ambulance, tow truck, police) — simulated for POC

The session initial_state must include:
    assignment_id:   int
    incident_type:   str  (e.g. "collision", "theft", "natural_disaster")
    incident_id:     int
    adjuster_id:     int
"""

from __future__ import annotations

# TODO (Phase 2): Import tools from .tools module and implement full agent
# from .tools import (
#     get_incident_procedures, get_similar_incidents,
#     log_field_note, escalate_to_supervisor,
# )
from google.adk.agents import Agent

from ...core import settings

field_guide_agent = Agent(
    model=settings.ROOT_AGENT_MODEL,
    name="field_guide",
    instruction="""
Eres el Guía de Campo de Slate — asistente especializado para ajustadores durante la atención
de siniestros en campo.

Tu responsabilidad:
1. Guiar al ajustador paso a paso según el tipo de siniestro del assignment activo.
2. Buscar casos similares para aprendizaje contextual.
3. Registrar notas de campo (log_field_note).
4. Escalar al supervisor cuando sea necesario (escalate_to_supervisor).
5. Coordinar servicios externos (ambulancia, grúa, policía) — simulado en POC.

Usa siempre el contexto del assignment en sesión (initial_state) para personalizar tus respuestas.
""",
    # tools=[
    #     get_incident_procedures, get_similar_incidents,
    #     log_field_note, escalate_to_supervisor,
    # ],
)
