"""Signs and verifies the short-lived token that carries the caller's identity
to the MCP server over the `x-vector-agent-token` header.

Deliberately standalone — this module must never import `server.web.core.config`
(or anything that does). That module reads the app's full DB_CONFIG at import
time; pulling it in here would mean the identity-check code path in the MCP
container transitively imports the superuser DSN, undoing the credential
separation the MCP server exists for. It reads its own secret,
AGENT_TOKEN_SECRET, directly from the environment instead.
"""
from __future__ import annotations

import os
import time

from jose import JWTError, jwt

ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 60
PURPOSE = "mcp-agent"


def _secret() -> str:
    try:
        return os.environ["AGENT_TOKEN_SECRET"]
    except KeyError as e:
        raise RuntimeError(
            "AGENT_TOKEN_SECRET is not set — required to sign/verify MCP agent tokens"
        ) from e


def mint_agent_token(user_id: int) -> str:
    """Called on the app-server side, once per MCP call, for the authenticated user."""
    payload = {
        "sub": str(user_id),
        "purpose": PURPOSE,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_agent_token(token: str | None) -> int:
    """Called on the MCP-server side. Raises PermissionError on any failure.

    Identity comes only from this token, never from a tool argument — a prompt
    injection in scraped job text can't make the caller name a different user_id.
    """
    if not token:
        raise PermissionError("missing agent token")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except JWTError as e:
        raise PermissionError(f"invalid agent token: {e}") from e
    if payload.get("purpose") != PURPOSE:
        raise PermissionError("wrong token purpose")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as e:
        raise PermissionError("agent token missing subject") from e
