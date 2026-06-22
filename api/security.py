"""API-key authentication.

Auth is enforced whenever ``API_KEY`` is set. Callers present the key via the
``X-API-Key`` header (or ``Authorization: Bearer <key>``). If the variable is
unset the API is open — convenient for local dev — but a warning is logged so
it is never silently unauthenticated in production. The endpoints trigger paid
LLM/compute work, so guard them in production.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

_API_KEY_ENV = "API_KEY"

if not os.environ.get(_API_KEY_ENV):
    logger.warning(
        "%s is not set — the API is UNAUTHENTICATED. Set %s to require an "
        "X-API-Key header.",
        _API_KEY_ENV,
        _API_KEY_ENV,
    )


def _extract_key(request: Request) -> str | None:
    header = request.headers.get("x-api-key")
    if header:
        return header
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.query_params.get("api_key")


async def require_api_key(request: Request) -> None:
    """FastAPI dependency that enforces the API key when configured."""
    expected = os.environ.get(_API_KEY_ENV)
    if not expected:
        return

    provided = _extract_key(request)
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
