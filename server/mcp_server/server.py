"""MCP server exposing read-only job-board queries to the agent runtime.

Runs as its own container (see docker-compose.yml: service `mcp-db`), reachable
only over the network at MCP_URL — never imported into the FastAPI process.
Its DB connection uses the `vector_agent` Postgres role (scripts/sql/create_agent_role.sql),
which physically cannot write and cannot read users.password: the regex checks
in run_select() below are ergonomics (a recoverable error instead of a raw
Postgres exception), not the security control. Deleting them changes nothing
about what this connection can do — the role grants are what enforce it.

Must not import server.web.core.config (see mcp/auth.py docstring) — this
module reads its DSN from AGENT_DB_DSN directly so it can never see the app's
superuser DB credentials.

Deliberately no `from __future__ import annotations` here (unlike the rest of
this codebase) — it turns every type hint into a string at runtime, and the
mcp SDK's tool registration does `issubclass(param.annotation, Context)` on
the raw signature without resolving those strings back to real types, which
crashes on any Optional/Union param.
"""

import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from mcp.server.fastmcp import Context, FastMCP

from server.mcp_server.auth import verify_agent_token

log = logging.getLogger("mcp")

DSN = os.environ["AGENT_DB_DSN"]  # vector_agent role — this container only
POOL = ThreadedConnectionPool(1, 10, dsn=DSN)
MAX_ROWS = 200

mcp = FastMCP("vector-db", host="0.0.0.0", port=int(os.getenv("MCP_PORT", 8100)))


@contextmanager
def _cursor():
    conn = POOL.getconn()
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        POOL.putconn(conn)


def _caller_user_id(ctx: Context) -> int:
    """Identity comes from the signed header the app server attaches, never
    from a tool argument — see verify_agent_token's docstring."""
    headers = ctx.request_context.request.headers
    token = headers.get("x-vector-agent-token")
    return verify_agent_token(token)


# ── tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
def search_jobs(
    role: Optional[str] = None,
    seniority: Optional[str] = None,
    location: Optional[str] = None,
    max_years: Optional[int] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Filter open jobs by structured criteria. Use this before run_select."""
    where, params = [], []
    if role:
        where.append("role ILIKE %s")
        params.append(f"%{role}%")
    if seniority:
        where.append("seniority = %s")
        params.append(seniority)
    if location:
        where.append("location ILIKE %s")
        params.append(f"%{location}%")
    if max_years is not None:
        where.append("yearsexperience <= %s")
        params.append(max_years)
    if keyword:
        where.append("keyword = %s")
        params.append(keyword)

    sql = (
        "SELECT id, title, company, location, url, role, seniority, "
        "yearsexperience, skills_must FROM jobs"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY scraped_at DESC LIMIT %s"
    params.append(min(limit, MAX_ROWS))

    with _cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


@mcp.tool()
def my_applications(ctx: Context, status: Optional[str] = None) -> list[dict]:
    """Applications belonging to the calling user. Status is scoped by the
    caller's identity, not by any argument — asking for another user's
    applications is not expressible through this tool."""
    uid = _caller_user_id(ctx)
    sql = (
        "SELECT a.id, a.status, a.applied_at, j.title, j.company "
        "FROM applications a JOIN jobs j ON j.id = a.job_id "
        "WHERE a.user_id = %s"
    )
    params: list[Any] = [uid]
    if status:
        sql += " AND a.status = %s"
        params.append(status)
    sql += " ORDER BY a.applied_at DESC LIMIT %s"
    params.append(MAX_ROWS)

    with _cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.I)


@mcp.tool()
def run_select(sql: str, params: Optional[list[Any]] = None) -> dict:
    """Run one read-only SELECT. Prefer search_jobs when it fits."""
    if ";" in sql.rstrip().rstrip(";"):
        return {"error": "one statement only"}
    if not _SELECT_ONLY.match(sql):
        return {"error": "SELECT/WITH only"}
    try:
        with _cursor() as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchmany(MAX_ROWS)
            return {"rows": [dict(r) for r in rows], "truncated": len(rows) == MAX_ROWS}
    except psycopg2.Error as e:
        # The read-only role rejects this at the database level regardless of
        # what reaches here — this is just a message the model can recover from.
        return {"error": str(e).strip()}


@mcp.tool()
def describe_schema() -> str:
    """Column listing for tables the agent may read. Reflects the vector_agent
    role's actual grants — e.g. users.password never appears here."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
        out: dict[str, list[str]] = {}
        for r in cur.fetchall():
            out.setdefault(r["table_name"], []).append(f'{r["column_name"]} {r["data_type"]}')
        return "\n".join(f"{t}({', '.join(c)})" for t, c in out.items())


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
