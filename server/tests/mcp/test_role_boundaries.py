"""Verifies the vector_agent Postgres role actually enforces what
scripts/sql/create_agent_role.sql grants — the real security boundary, not
application code. Run against a database where that script has already been
applied (see the script's header for the psql invocation).

Skipped unless AGENT_DB_DSN is set, so `pytest server/tests/` still passes on
a machine that hasn't provisioned the role. Wire AGENT_DB_DSN into CI once the
role exists there, so a future migration that re-grants writes fails the build.
"""
import os

import psycopg2
import psycopg2.errors
import pytest

AGENT_DB_DSN = os.environ.get("AGENT_DB_DSN")

pytestmark = pytest.mark.skipif(
    not AGENT_DB_DSN, reason="AGENT_DB_DSN not set — vector_agent role not provisioned here"
)


@pytest.fixture
def agent_conn():
    conn = psycopg2.connect(AGENT_DB_DSN)
    yield conn
    conn.close()


def test_agent_role_cannot_write(agent_conn):
    with pytest.raises((psycopg2.errors.InsufficientPrivilege, psycopg2.errors.ReadOnlySqlTransaction)):
        with agent_conn.cursor() as cur:
            cur.execute("UPDATE applications SET status = 'ghosted'")


def test_agent_role_cannot_insert(agent_conn):
    with pytest.raises((psycopg2.errors.InsufficientPrivilege, psycopg2.errors.ReadOnlySqlTransaction)):
        with agent_conn.cursor() as cur:
            cur.execute("INSERT INTO applications (user_id, job_id) VALUES (1, 'x')")


def test_password_column_unreadable(agent_conn):
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with agent_conn.cursor() as cur:
            cur.execute("SELECT password FROM users LIMIT 1")


def test_email_column_readable(agent_conn):
    """Sanity check the role isn't just broken outright — the explicitly
    granted columns on `users` should still be selectable."""
    with agent_conn.cursor() as cur:
        cur.execute("SELECT id, email, created_at FROM users LIMIT 1")


def test_agent_evaluations_table_unreadable(agent_conn):
    """Internal eval data was never granted — only jobs/applications/resumes
    and the users column subset were."""
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with agent_conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_evaluations LIMIT 1")


# ── run_select's input guards ────────────────────────────────────────────
# These reject before ever touching the DB, but importing the module still
# needs AGENT_DB_DSN reachable (it opens a connection pool at import time),
# hence living in this skipped-without-a-DB file rather than test_auth.py.

def test_run_select_rejects_stacked_statements():
    from server.mcp.server import run_select

    result = run_select(sql="SELECT 1; DROP TABLE jobs;")
    assert "error" in result


def test_run_select_rejects_non_select():
    from server.mcp.server import run_select

    result = run_select(sql="DELETE FROM jobs")
    assert "error" in result


def test_run_select_allows_plain_select(agent_conn):
    from server.mcp.server import run_select

    result = run_select(sql="SELECT 1 AS one")
    assert result["rows"] == [{"one": 1}]
