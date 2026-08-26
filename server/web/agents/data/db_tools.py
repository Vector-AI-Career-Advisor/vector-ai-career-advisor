"""DB Tools — all structured database query tools for the SQL Agent."""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import psycopg2
import psycopg2.extras
from langchain.tools import tool

from server.db.postgres import get_connection
from server.db.chroma import init_chroma, search_jobs as chroma_search
from server.web.agents.tools.mcp_client import MCP_TOOLS

log = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────

def _conn():
    return get_connection()


_chroma_collection = None
_chroma_lock = threading.Lock()

def _collection():
    global _chroma_collection
    if _chroma_collection is None:
        with _chroma_lock:
            if _chroma_collection is None:
                _chroma_collection = init_chroma()
    return _chroma_collection


def _run_query(sql: str, params: tuple = (), description: str = ""):
    """Safely runs SQL using parameterised queries to prevent SQL injection."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description] if cur.description else []
    finally:
        conn.close()
    return {"description": description, "columns": cols, "rows": [dict(r) for r in rows]}


# ── tools ─────────────────────────────────────────────────────────────────

@tool
def semantic_search_jobs(query: str, n_results: int = 5):
    """Search jobs using semantic similarity (vector search).
    Use for: finding jobs by natural-language description, skill match, or profile.
    Examples: 'find Python server jobs', 'jobs at fintech startups'
    """
    try:
        collection = _collection()
        hits = chroma_search(collection, query, n_results=n_results)
    except Exception as e:
        log.warning("ChromaDB unavailable, semantic search skipped: %s", e)
        return {"jobs": [], "note": "Semantic search unavailable; use search_jobs_by_criteria instead."}

    job_ids = [h["metadata"]["job_id"] for h in hits]

    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title, company, role, location, url, description FROM jobs WHERE id = ANY(%s)",
                (job_ids,),
            )
            rows = {r["id"]: dict(r) for r in cur.fetchall()}
    finally:
        conn.close()

    return {"jobs": [rows[jid] for jid in job_ids if jid in rows]}


@tool
def get_job_details(job_ids: list[str]):
    """Get full job details for given job IDs.
    Use after search results return IDs the user wants to know more about.
    """
    return _run_query(
        "SELECT * FROM jobs WHERE id = ANY(%s)",
        (job_ids,),
        "Fetch full job details",
    )


@tool
def get_job_aggregate(operation: str, column: str, role_filter: Optional[str] = None):
    """Calculate COUNT, AVG, MIN, or MAX statistics on job data.
    - operation: one of ['COUNT', 'AVG', 'MIN', 'MAX']
    - column: use '*' for total row counts (e.g. COUNT(*)); or one of ['id', 'yearsexperience', 'posted_at', 'scraped_at']
      IMPORTANT: always use column='*' or column='id' when counting total listings — never column='yearsexperience' for counts, as that column has NULLs and will undercount.
    - role_filter: optional role name to filter (e.g. 'data scientist')
    """
    ALLOWED_OPS = {"COUNT", "AVG", "MIN", "MAX"}
    ALLOWED_COLUMNS = {"*", "yearsexperience", "posted_at", "scraped_at", "id"}

    op_upper = operation.upper()
    col_lower = column.lower()

    if op_upper not in ALLOWED_OPS:
        return {"error": f"Operation '{operation}' not allowed. Use COUNT, AVG, MIN, or MAX."}
    if col_lower not in ALLOWED_COLUMNS:
        return {"error": f"Column '{column}' not allowed for calculations."}
    if col_lower == "*" and op_upper != "COUNT":
        return {"error": "column='*' is only valid with COUNT."}

    sql = f"SELECT {op_upper}({col_lower}) AS result FROM jobs WHERE 1=1"
    params = []

    if role_filter:
        words = role_filter.split()
        or_conditions = [f"LOWER(role) LIKE LOWER(%s)" for _ in words]
        params.extend(f"%{w}%" for w in words)
        sql += f" AND ({' OR '.join(or_conditions)})"

    return _run_query(sql, tuple(params), f"{op_upper} of {col_lower}")


@tool
def get_column_distribution(column: str, limit: int = 15):
    """Get top items and their counts for a given column.
    - column: one of ['role', 'seniority', 'location', 'company', 'yearsexperience']
    Examples: top companies, seniority breakdown, most common roles
    """
    ALLOWED_COLUMNS = {"role", "seniority", "location", "company", "yearsexperience"}
    col_lower = column.lower()

    if col_lower not in ALLOWED_COLUMNS:
        return {"error": f"Cannot group by column '{column}'."}

    return _run_query(
        f"""
        SELECT {col_lower} AS item, COUNT(*) AS count
        FROM jobs WHERE {col_lower} IS NOT NULL
        GROUP BY {col_lower} ORDER BY count DESC LIMIT %s
        """,
        (limit,),
        f"Distribution of {col_lower}",
    )


@tool
def search_jobs_by_criteria(
    role: Optional[str] = None,
    location: Optional[str] = None,
    company: Optional[str] = None,
    max_experience: Optional[int] = None,
):
    """Filter jobs by specific fields.
    - role: e.g. 'server', 'react developer'
    - location: e.g. 'Tel Aviv', 'remote' — ONLY use when the user explicitly names a city, country, or region (e.g. 'in Tel Aviv', 'remote jobs'). Do NOT use for company names.
    - company: e.g. 'Google', 'startup' — use when the user names a company or employer (e.g. 'at Google', 'jobs at Abra'). When in doubt between location and company, prefer company.
    - max_experience: maximum years of experience required
    """
    sql = "SELECT id, title, company, role, location, url FROM jobs"
    conditions, params = [], []

    if role:
        conditions.append("LOWER(role) LIKE LOWER(%s)")
        params.append(f"%{role}%")
    if location:
        conditions.append("LOWER(location) LIKE LOWER(%s)")
        params.append(f"%{location}%")
    if company:
        conditions.append("LOWER(company) LIKE LOWER(%s)")
        params.append(f"%{company}%")
    if max_experience is not None:
        conditions.append("yearsexperience <= %s")
        params.append(max_experience)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY scraped_at DESC LIMIT %s"
    params.append(10)

    return _run_query(sql, tuple(params), "Filtered job search")


@tool
def top_skills(role: str, limit: int = 10):
    """Get the most required skills for a specific role."""
    return _run_query(
        """
        SELECT unnest(skills_must) AS skill, COUNT(*) AS cnt
        FROM jobs WHERE LOWER(role) = LOWER(%s)
        GROUP BY skill ORDER BY cnt DESC LIMIT %s
        """,
        (role, limit),
        f"Top skills for {role}",
    )


@tool
def top_skills_all(limit: int = 15):
    """Get the most required skills across all jobs in the database."""
    return _run_query(
        """
        SELECT unnest(skills_must) AS skill, COUNT(*) AS cnt
        FROM jobs GROUP BY skill ORDER BY cnt DESC LIMIT %s
        """,
        (limit,),
        "Top skills overall",
    )


DB_TOOLS = [
    semantic_search_jobs,
    get_job_details,
    get_job_aggregate,
    get_column_distribution,
    search_jobs_by_criteria,
    top_skills,
    top_skills_all,
    *MCP_TOOLS,
]
