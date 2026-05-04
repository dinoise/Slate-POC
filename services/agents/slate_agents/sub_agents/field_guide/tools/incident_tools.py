"""Field guide tools: incident details and procedures."""

from __future__ import annotations

import httpx

from ....core.config import settings
from ....core.http_auth import get_api_headers
from ....core.logging import get_logger

logger = get_logger(__name__)

# ── Incident type procedures ──────────────────────────────────────────────────

_PROCEDURES: dict[str, list[str]] = {
    "collision": [
        "1. Asegurar la seguridad de todas las partes involucradas.",
        "2. Verificar si hay heridos y solicitar ambulancia si es necesario.",
        "3. Documentar la escena con fotografías: daños, posición de vehículos, señalización.",
        "4. Recopilar datos de los involucrados: nombre, póliza, placas, licencia.",
        "5. Levantar el informe de siniestro con número de expediente.",
        "6. Coordinar grúa si algún vehículo no puede circular.",
        "7. Registrar testigos y sus declaraciones.",
    ],
    "theft": [
        "1. Verificar que el lugar es seguro antes de inspeccionar.",
        "2. No tocar ni mover evidencia hasta la llegada de la policía.",
        "3. Solicitar número de denuncia ante el Ministerio Público.",
        "4. Documentar daños y bienes sustraídos con fotografías.",
        "5. Recopilar declaración del asegurado.",
        "6. Revisar existencia de cámaras de vigilancia en la zona.",
        "7. Iniciar proceso de reclamación con el número de denuncia.",
    ],
    "natural_disaster": [
        "1. Evaluar seguridad estructural antes de ingresar al inmueble.",
        "2. Documentar la magnitud del siniestro (inundación, granizo, sismo, etc.).",
        "3. Fotografiar todos los daños: exterior, interior, pertenencias afectadas.",
        "4. Verificar servicios de emergencia activos en la zona.",
        "5. Registrar fecha y hora estimada del evento.",
        "6. Solicitar reportes meteorológicos o sismológicos oficiales.",
        "7. Estimar pérdidas totales con inventario inicial.",
    ],
    "fire": [
        "1. Confirmar que el fuego está completamente extinguido antes de inspeccionar.",
        "2. Coordinar con bomberos para acceso seguro y su reporte oficial.",
        "3. Documentar el origen aparente del incendio.",
        "4. Fotografiar toda la extensión de daños por fuego y humo.",
        "5. Identificar bienes salvables vs pérdida total.",
        "6. Verificar cobertura de habitación temporal si aplica.",
        "7. Iniciar proceso de reclamación con reporte de bomberos.",
    ],
    "vandalism": [
        "1. Verificar la seguridad del lugar.",
        "2. Presentar denuncia ante autoridades locales.",
        "3. Documentar todos los daños con fotografías.",
        "4. Obtener número de denuncia oficial.",
        "5. Recopilar testimonios de testigos si los hay.",
        "6. Estimar costo de reparación o reposición.",
    ],
}

_DEFAULT_PROCEDURES = [
    "1. Verificar la seguridad del lugar y de las personas involucradas.",
    "2. Documentar el siniestro con fotografías detalladas.",
    "3. Recopilar información de todas las partes involucradas.",
    "4. Levantar el informe de siniestro.",
    "5. Coordinar los servicios necesarios según el caso.",
]


# ── Tools ─────────────────────────────────────────────────────────────────────


async def get_incident_details(tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Fetches full details of the incident linked to the active assignment.

    Reads incident_id from the session state and calls slate-api to get the
    incident record: type, description, location, status, and timestamps.

    Returns:
        dict with incident details, or an error dict if the request fails.
    """
    incident_id = tool_context.state.get("incident_id")
    logger.info("get_incident_details called | incident_id=%s", incident_id)

    if not incident_id:
        logger.error(
            "get_incident_details: incident_id missing from session state. "
            "assignment_id=%s agent_type=%s",
            tool_context.state.get("assignment_id"),
            tool_context.state.get("agent_type"),
        )
        return {"error": "incident_id not found in session state"}

    url = f"{settings.SLATE_API_URL}/api/v1/incidents/{incident_id}"
    logger.debug("get_incident_details: GET %s", url)

    try:
        headers = get_api_headers()
        logger.debug("get_incident_details: headers keys=%s", list(headers.keys()))
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
        logger.info(
            "get_incident_details: response status=%s incident_id=%s",
            response.status_code,
            incident_id,
        )
        response.raise_for_status()
        data = response.json()
        logger.debug(
            "get_incident_details: response body keys=%s",
            list(data.keys()) if isinstance(data, dict) else type(data),
        )
        return data
    except httpx.HTTPStatusError as exc:
        logger.error(
            "get_incident_details: HTTP error %s for incident_id=%s | body=%s",
            exc.response.status_code,
            incident_id,
            exc.response.text[:200],
        )
        return {"error": f"API returned {exc.response.status_code}", "incident_id": incident_id}
    except httpx.TimeoutException:
        logger.error("get_incident_details: timeout calling %s", url)
        return {"error": "Request timed out", "incident_id": incident_id}
    except Exception as exc:
        logger.exception("get_incident_details: unexpected error | incident_id=%s", incident_id)
        return {"error": str(exc), "incident_id": incident_id}


def get_incident_procedures(tool_context) -> dict:  # type: ignore[no-untyped-def]
    """Returns the step-by-step procedures for the current assignment's incident type.

    Reads incident_type from the session state and returns the corresponding
    protocol checklist. Works offline — no API call needed.

    Returns:
        dict with:
            - incident_type: the type used for lookup
            - procedures: list of numbered steps to follow
            - note: advisory note if type is unknown
    """
    incident_type = tool_context.state.get("incident_type", "").lower()
    logger.info("get_incident_procedures called | incident_type=%s", incident_type or "<empty>")

    procedures = _PROCEDURES.get(incident_type)

    if procedures:
        logger.debug(
            "get_incident_procedures: found %d steps for type=%s", len(procedures), incident_type
        )
        return {"incident_type": incident_type, "procedures": procedures}

    logger.warning(
        "get_incident_procedures: unknown incident_type=%r — falling back to generic procedures",
        incident_type,
    )
    return {
        "incident_type": incident_type or "desconocido",
        "procedures": _DEFAULT_PROCEDURES,
        "note": f"Tipo '{incident_type}' no tiene protocolo específico. Usando protocolo general.",
    }
