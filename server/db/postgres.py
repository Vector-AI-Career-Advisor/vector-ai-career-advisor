from __future__ import annotations
import json
import logging
from datetime import date
from typing import List, Optional
import psycopg2
from psycopg2.extras import execute_values
from server.web.core.config import DB_CONFIG

log = logging.getLogger(__name__)


2# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db(conn=None) -> None:
    """Create all required tables and indexes. Accepts an optional existing connection."""
    _own_conn = conn is None
    if _own_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id         SERIAL PRIMARY KEY,
                    email      TEXT UNIQUE NOT NULL,
                    password   TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    filename    TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    updated_at  TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id               TEXT PRIMARY KEY,
                    title            TEXT,
                    role             TEXT,
                    seniority        TEXT,
                    company          TEXT,
                    location         TEXT,
                    url              TEXT,
                    description      TEXT,
                    skills_must      TEXT[],
                    skills_nice      TEXT[],
                    yearsexperience  INTEGER,
                    past_experience  TEXT[],
                    keyword          TEXT,
                    source           TEXT DEFAULT 'linkedin',
                    posted_at        DATE,
                    scraped_at       TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS logo_url TEXT;")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS jobs_scraped_date_idx ON jobs ((scraped_at::date));
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS jobs_keyword_idx ON jobs (keyword);")
            cur.execute("CREATE INDEX IF NOT EXISTS jobs_role_idx ON jobs (role);")
            cur.execute("CREATE INDEX IF NOT EXISTS jobs_seniority_idx ON jobs (seniority);")

            # ── Agent evaluations ─────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_evaluations (
                    id                 SERIAL PRIMARY KEY,
                    agent_type         TEXT    NOT NULL,
                    score              INTEGER NOT NULL,
                    passed             BOOLEAN NOT NULL,
                    dimensions         JSONB,
                    critique           TEXT,
                    suggested_response TEXT,
                    user_message       TEXT,
                    agent_response     TEXT,
                    evaluated_at       TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS evals_agent_type_idx ON agent_evaluations (agent_type);")
            cur.execute("CREATE INDEX IF NOT EXISTS evals_evaluated_at_idx ON agent_evaluations (evaluated_at);")

            # ── Applications ──────────────────────────────────────────────────
            cur.execute("""
                DO $$ BEGIN
                    CREATE TYPE application_status AS ENUM (
                        'applied',
                        'screening',
                        'interview',
                        'offer',
                        'rejected',
                        'withdrawn'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_id       TEXT    NOT NULL REFERENCES jobs(id)  ON DELETE CASCADE,
                    status       application_status NOT NULL DEFAULT 'applied',
                    applied_at   TIMESTAMP DEFAULT NOW(),
                    updated_at   TIMESTAMP DEFAULT NOW(),
                    notes        TEXT,
                    UNIQUE (user_id, job_id)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS applications_user_idx   ON applications (user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS applications_status_idx ON applications (status);")

        conn.commit()
    finally:
        if _own_conn:
            conn.close()
    log.info("DB schema and indexes ready.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            log.warning("Could not parse posted_at value '%s' — storing NULL.", val)
            return None
    return None


# ── Writes ────────────────────────────────────────────────────────────────────

def insert_jobs(conn, jobs: List[dict]) -> int:
    """Insert jobs, silently skip duplicates. Returns number of rows sent."""
    if not jobs:
        return 0

    rows = [
        (
            j["id"], j["title"], j.get("role"), j.get("seniority"),
            j["company"], j["location"], j["url"],
            j.get("description"),
            j.get("skills_must", []), j.get("skills_nice", []),
            j.get("yearsexperience"),
            j.get("past_experience", []),
            j["keyword"], j.get("source", "linkedin"),
            _to_date(j.get("posted_at")),
            j.get("logo_url"),
        )
        for j in jobs
    ]

    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO jobs (
                id, title, role, seniority, company, location, url,
                description, skills_must, skills_nice, yearsexperience,
                past_experience, keyword, source, posted_at, logo_url
            )
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                logo_url = EXCLUDED.logo_url
                WHERE jobs.logo_url IS NULL AND EXCLUDED.logo_url IS NOT NULL;
        """, rows)
    conn.commit()
    log.info("Inserted %d jobs into PostgreSQL.", len(rows))
    return len(rows)


# ── Applications — Writes ─────────────────────────────────────────────────────

_VALID_STATUSES = {"applied", "screening", "interview", "offer", "rejected", "withdrawn"}


def add_application(conn, user_id: int, job_id: str, notes: Optional[str] = None) -> dict:
    """Create a new application with status 'applied'. Raises if already exists."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO applications (user_id, job_id, notes)
            VALUES (%s, %s, %s)
            RETURNING id, user_id, job_id, status, applied_at, updated_at, notes;
        """, (user_id, job_id, notes))
        cols = [desc[0] for desc in cur.description]
        row = dict(zip(cols, cur.fetchone()))
    conn.commit()
    log.info("User %d applied to job %s (application id=%d).", user_id, job_id, row["id"])
    return row


def update_application_status(
    conn, user_id: int, job_id: str, status: str, notes: Optional[str] = None
) -> dict:
    """Update status (and optionally notes) for an existing application."""
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {_VALID_STATUSES}")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE applications
            SET status     = %s,
                notes      = COALESCE(%s, notes),
                updated_at = NOW()
            WHERE user_id = %s AND job_id = %s
            RETURNING id, user_id, job_id, status, applied_at, updated_at, notes;
        """, (status, notes, user_id, job_id))
        row_data = cur.fetchone()
        if row_data is None:
            raise ValueError(f"No application found for user_id={user_id}, job_id={job_id!r}.")
        cols = [desc[0] for desc in cur.description]
        row = dict(zip(cols, row_data))
    conn.commit()
    log.info("Application id=%d updated to status '%s'.", row["id"], status)
    return row


def delete_application(conn, user_id: int, job_id: str) -> bool:
    """Remove an application. Returns True if a row was deleted."""
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM applications WHERE user_id = %s AND job_id = %s;
        """, (user_id, job_id))
        deleted = cur.rowcount > 0
    conn.commit()
    if deleted:
        log.info("Deleted application for user_id=%d, job_id=%s.", user_id, job_id)
    else:
        log.warning("delete_application: no row matched user_id=%d, job_id=%s.", user_id, job_id)
    return deleted


# ── Applications — Reads ──────────────────────────────────────────────────────

def fetch_applications_by_user(
    conn, user_id: int, status: Optional[str] = None
) -> List[dict]:
    """Return all applications for a user, joined with job details.
    Optionally filter by status."""
    if status is not None and status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {_VALID_STATUSES}")

    query = """
        SELECT
            a.id            AS application_id,
            a.status,
            a.applied_at,
            a.updated_at,
            a.notes,
            j.id            AS job_id,
            j.title,
            j.company,
            j.location,
            j.url,
            j.role,
            j.seniority,
            j.logo_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.user_id = %s
    """
    params: list = [user_id]

    if status is not None:
        query += " AND a.status = %s"
        params.append(status)

    query += " ORDER BY a.applied_at DESC;"

    with conn.cursor() as cur:
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_application(conn, user_id: int, job_id: str) -> Optional[dict]:
    """Return a single application row joined with job details, or None."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                a.id            AS application_id,
                a.status,
                a.applied_at,
                a.updated_at,
                a.notes,
                j.id            AS job_id,
                j.title,
                j.company,
                j.location,
                j.url,
                j.role,
                j.seniority,
                j.logo_url
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            WHERE a.user_id = %s AND a.job_id = %s;
        """, (user_id, job_id))
        row_data = cur.fetchone()
        if row_data is None:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row_data))


def count_applications_by_user(conn, user_id: int) -> dict:
    """Return a breakdown of application counts by status for a user."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status, COUNT(*) AS total
            FROM applications
            WHERE user_id = %s
            GROUP BY status;
        """, (user_id,))
        return {row[0]: row[1] for row in cur.fetchall()}


# ── Reads ─────────────────────────────────────────────────────────────────────

def count_jobs(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jobs")
        return cur.fetchone()[0]


def count_jobs_today(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM jobs WHERE scraped_at::date = %s",
            (date.today(),),
        )
        return cur.fetchone()[0]


def fetch_all_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM jobs;")
        return {row[0] for row in cur.fetchall()}


def fetch_jobs_by_ids(conn, ids: List[str]) -> List[dict]:
    if not ids:
        return []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, role, seniority, company, location, url,
                   description, skills_must, skills_nice, yearsexperience,
                   past_experience, keyword, source, posted_at, logo_url
            FROM jobs
            WHERE id = ANY(%s);
        """, (ids,))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def insert_evaluation(
    conn,
    agent_type: str,
    user_message: str,
    agent_response: str,
    score: int,
    passed: bool,
    dimensions: dict,
    critique: str,
    suggested_response: str,
) -> int:
    """Insert one agent evaluation row. Returns the new row id."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO agent_evaluations
                (agent_type, score, passed, dimensions, critique,
                 suggested_response, user_message, agent_response)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            agent_type, score, passed,
            json.dumps(dimensions),
            critique, suggested_response,
            user_message, agent_response,
        ))
        row_id = cur.fetchone()[0]
    conn.commit()
    log.debug("Evaluation saved (id=%d, agent=%s, score=%d).", row_id, agent_type, score)
    return row_id


def fetch_jobs_missing_from_chroma(conn, chroma_job_ids: set) -> List[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM jobs;")
        all_ids = [row[0] for row in cur.fetchall()]

    missing_ids = [jid for jid in all_ids if jid not in chroma_job_ids]
    log.info("%d jobs missing from ChromaDB — backfilling.", len(missing_ids))
    return fetch_jobs_by_ids(conn, missing_ids)