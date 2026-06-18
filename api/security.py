"""API-key authentication for the review and trace endpoints.

Auth is enforced whenever the ``REVIEW_API_KEY`` environment variable
is set. Callers must then present the key via the ``X-API-Key`` header
(or an ``api_key`` query param, which the dashboard uses). If the
variable is unset the API is open — convenient for local development,
but a warning is logged at import time so it is never silently
unauthenticated in production.

The review endpoint triggers paid LLM/compute work and the trace
endpoints expose submitted source code, so both must be guarded.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

_API_KEY_ENV = "REVIEW_API_KEY"

if not os.environ.get(_API_KEY_ENV):
    logger.warning(
        "%s is not set — /reviews and trace APIs are UNAUTHENTICATED. "
        "Set %s to require an X-API-Key header.",
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
