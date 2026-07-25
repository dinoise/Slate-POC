"""Coordinator sub-agent — Phase 3 implementation.

Assists dispatchers (admin) with:
- Overview of active assignments
- Adjuster availability and load balancing
- Demand forecasting
- Rebalancing suggestions (POST /api/v1/recommendations/)
- Assignment creation and status updates

The session initial_state should include:
    dispatcher_id:  int
    current_shift:  str  (e.g. "morning", "afternoon", "night")
"""

from __future__ import annotations

# TODO (Phase 3): Import tools and implement full agent
# from .tools import get_active_assignments, get_adjuster_availability, suggest_rebalancing
from google.adk.agents import Agent

from ...core import settings

coordinator_agent = Agent(
    model=settings.ROOT_AGENT_MODEL,
    name="coordinator",
    instruction="""
Eres el Coordinador de Operaciones de Slate — asistente especializado para despachadores
que supervisan múltiples asignaciones simultáneas.

Tu responsabilidad:
1. Monitorear el estado de assignments activos.
2. Identificar ajustadores disponibles y su carga de trabajo.
3. Sugerir reasignaciones o balanceo de carga.
4. Responder consultas sobre demanda predicha por zona.
5. Crear o actualizar assignments según instrucciones del despachador.
""",
    # tools=[
    #     get_active_assignments, get_adjuster_availability,
    #     suggest_rebalancing, create_assignment,
    # ],
)
