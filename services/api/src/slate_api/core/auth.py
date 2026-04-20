"""Google ID token verification for end-user authentication."""

import base64
import json
from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

# Reusable Google transport request — not thread-unsafe, create once per process
_google_request = google_requests.Request()


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _peek_audience(token: str) -> str | None:
    """Lee el campo 'aud' del payload JWT sin verificar la firma.

    Permite seleccionar el client ID correcto antes de llamar a
    verify_oauth2_token, evitando iterar sobre todos los IDs registrados.
    El valor no es de confianza hasta que la firma se verifique — solo
    se usa para elegir qué audience pasar a la verificación criptográfica.
    """
    try:
        payload_b64 = token.split(".")[1]
        # JWT usa base64url sin padding — añadimos el padding necesario
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("aud")
    except Exception:
        return None


def verify_google_token(request: Request) -> Mapping[str, Any]:
    """
    FastAPI dependency — verifica el Google ID token del header Authorization.

    Extrae el campo 'aud' del JWT sin verificar (O(1)) para seleccionar
    el client ID correcto y luego verifica la firma criptográfica una sola vez.

    Raises 401 si:
    - No hay token
    - El audience no está en la lista de client IDs permitidos
    - El token es inválido, expirado o tiene firma incorrecta

    Returns el dict de claims verificados (incluye 'sub', 'email', 'name').
    """
    client_ids = settings.google_client_ids
    if not client_ids:
        logger.warning("GOOGLE_CLIENT_ID not set — skipping token verification")
        return {"sub": "dev", "email": "dev@local"}

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Lookup O(1): leer aud del JWT y buscar en el set de IDs permitidos
    client_ids_set = set(client_ids)
    audience = _peek_audience(token)
    if audience not in client_ids_set:
        logger.warning("Token audience '%s' not in allowed client IDs", audience)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            _google_request,
            audience=audience,
            clock_skew_in_seconds=10,
        )
        return claims
    except ValueError as e:
        logger.warning("Invalid Google ID token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# Typed dependency alias for use in route signatures
CurrentUser = Annotated[dict, Depends(verify_google_token)]
