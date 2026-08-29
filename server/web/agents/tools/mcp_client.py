"""LangChain-facing bridge to the MCP server (server/mcp) — the agent
runtime's path to user-scoped and freeform-SQL database reads, isolated from
the app's own DB credentials (the `server` container never holds the
vector_agent DSN; it only knows the network address MCP_URL).

Bridges the MCP SDK's async client into this codebase's synchronous LangChain
@tool / ToolNode pattern: each call opens a session, calls one tool, and closes
it via asyncio.run(). These tools are invoked from the background thread
router.py spawns per chat request (see web/features/agents/router.py), which has
no event loop of its own, so asyncio.run() here is safe.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextvars import ContextVar, Token
from typing import Any, Optional

from langchain.tools import tool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from server.mcp_server.auth import mint_agent_token

log = logging.getLogger("agents.mcp_client")

# Same override convention as web/core/config.py's DB_HOST/DOCKER_DB_HOST and
# OLLAMA_BASE_URL/DOCKER_OLLAMA_URL: DOCKER_MCP_URL is set by docker-compose
# for the containerized network address; MCP_URL is the plain-.env fallback
# for running the server outside Docker.
MCP_URL = os.getenv("DOCKER_MCP_URL") or os.getenv("MCP_URL", "http://localhost:8100/mcp")

# Per-request identity. A ContextVar rather than a module-level dict (contrast
# resume_tools._context) because — unlike that one, which is only ever set and
# read on the same request's dedicated thread — this value feeds a signed
# token that authorizes DB reads as a specific user. A shared mutable dict set
# from the shared asyncio route handler would let a concurrent request
# overwrite it before a slower request's thread reads it, minting a token for
# the wrong user. Each chat request runs its own native thread (see
# web/features/agents/router.py), and threading.Thread starts with its own fresh
# Context, so a ContextVar set inside that thread is naturally isolated.
_current_user: ContextVar[Optional[int]] = ContextVar("mcp_agent_user", default=None)


def set_current_user(user_id: int) -> Token:
    return _current_user.set(user_id)


def reset_current_user(token: Token) -> None:
    _current_user.reset(token)


async def _call(name: str, args: dict) -> tuple[str, bool]:
    headers = {}
    user_id = _current_user.get()
    if user_id is not None:
        # Identity travels only in this signed header, never as a tool
        # argument — see mcp/auth.py and mcp/server.py.
        headers["x-vector-agent-token"] = mint_agent_token(int(user_id))

    async with streamable_http_client(MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args)
            text = "\n".join(c.text for c in result.content if c.type == "text")
            return text, bool(result.isError)


def _call_sync(name: str, args: dict[str, Any]) -> str:
    try:
        text, is_error = asyncio.run(_call(name, args))
    except Exception as e:
        log.error("MCP call to %r failed: %s", name, e)
        return f"MCP call to '{name}' failed: {e}"
    return text if not is_error else f"MCP tool error: {text}"


@tool
def my_applications(status: Optional[str] = None) -> str:
    """Get the current user's job applications, optionally filtered by status
    (e.g. 'applied', 'interviewing', 'rejected', 'offer'). Scoped automatically
    to the logged-in user via the MCP server — there is no argument for another
    user's ID, so another user's applications cannot be requested through this tool.
    """
    return _call_sync("my_applications", {"status": status} if status else {})


@tool
def run_sql_query(sql: str) -> str:
    """Run one freeform read-only SELECT against the job database, for questions
    the other DB tools can't express. SELECT/WITH only, one statement — writes
    and multi-statement input are rejected by the MCP server. Prefer the other
    DB tools when they fit; call describe_schema first if unsure of column names.
    """
    return _call_sync("run_select", {"sql": sql})


@tool
def describe_schema() -> str:
    """List the tables and columns available to query via run_sql_query."""
    return _call_sync("describe_schema", {})


MCP_TOOLS = [my_applications, run_sql_query, describe_schema]
