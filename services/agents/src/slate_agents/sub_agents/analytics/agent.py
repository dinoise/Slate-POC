"""Analytics sub-agent — Phase 5 implementation.

Provides conversational analytics for the Observatory (admin):
- Proactive anomaly detection
- Natural language queries over operational metrics
- Shift summary generation
- Time-series trend analysis

Requires new analytics endpoints in slate-api (GET /api/v1/analytics/...).
"""

from __future__ import annotations

# TODO (Phase 5): Import tools and implement full agent
# from .tools import query_metrics, detect_anomalies, generate_shift_summary
from google.adk.agents import Agent

from ...core import settings

analytics_agent = Agent(
    model=settings.ROOT_AGENT_MODEL,
    name="analytics",
    instruction="""
Eres el agente de Analítica de Slate — asistente conversacional para análisis operacional
en el Observatory del panel de administración.

Tu responsabilidad:
1. Responder preguntas sobre métricas operacionales (tiempos de respuesta, volumen, cobertura).
2. Detectar anomalías en patrones de demanda o desempeño.
3. Generar resúmenes de turno a solicitud del despachador.
4. Identificar tendencias y áreas de mejora.

Presenta los datos de forma clara con tablas o listas cuando sea apropiado.
""",
    # tools=[query_metrics, detect_anomalies, generate_shift_summary],
)
