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
                    first_name TEXT,
                    last_name  TEXT,
                    phone      TEXT,
                    city       TEXT,
                    years_experience INTEGER,
                    career_stage TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS city TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS years_experience INTEGER;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS career_stage TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();")
            
            # ── OAuth Identities ───────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS oauth_identities (
                    id                 SERIAL PRIMARY KEY,
                    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider           TEXT NOT NULL,
                    provider_user_id   TEXT NOT NULL,
                    created_at         TIMESTAMP DEFAULT NOW(),
                    UNIQUE (provider, provider_user_id)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS oauth_identities_user_idx ON oauth_identities (user_id);")
            
            
            # ── User Profile Tables ────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_educations (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    degree_type TEXT,
                    field_of_study TEXT,
                    school TEXT,
                    graduation_year INTEGER,
                    relevant_courses TEXT,
                    academic_highlights TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_educations_user_idx ON user_educations (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_skills (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    skill      TEXT NOT NULL,
                    category   TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (user_id, skill)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_skills_user_idx ON user_skills (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_soft_skills (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    skill      TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (user_id, skill)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_soft_skills_user_idx ON user_soft_skills (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_languages (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    language   TEXT NOT NULL,
                    proficiency TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (user_id, language)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_languages_user_idx ON user_languages (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_work_experience (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    position   TEXT,
                    company    TEXT,
                    start_date DATE,
                    end_date   DATE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_work_experience_user_idx ON user_work_experience (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_certifications (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    certification TEXT NOT NULL,
                    issuer     TEXT,
                    date_obtained DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_certifications_user_idx ON user_certifications (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_volunteering (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role       TEXT NOT NULL,
                    organization TEXT,
                    start_date DATE,
                    end_date   DATE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_volunteering_user_idx ON user_volunteering (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_clubs_orgs (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name       TEXT NOT NULL,
                    role       TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_clubs_orgs_user_idx ON user_clubs_orgs (user_id);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    github_url TEXT,
                    portfolio_url TEXT,
                    work_preferences JSONB,
                    interests JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS user_preferences_user_idx ON user_preferences (user_id);")
            
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
            # resumes: many-per-user, titled, exactly one active per user
            cur.execute("ALTER TABLE resumes DROP CONSTRAINT IF EXISTS resumes_user_id_key;")
            cur.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS title     TEXT;")
            cur.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute("CREATE INDEX IF NOT EXISTS resumes_user_idx ON resumes (user_id);")
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS resumes_one_active_per_user "
                "ON resumes (user_id) WHERE is_active;"
            )
            cur.execute("UPDATE resumes SET title = 'Resume ' || id WHERE title IS NULL;")
            cur.execute("""
                UPDATE resumes SET is_active = TRUE
                 WHERE id IN (
                     SELECT DISTINCT ON (user_id) id FROM resumes
                     ORDER BY user_id, uploaded_at DESC
                 )
                   AND NOT EXISTS (
                     SELECT 1 FROM resumes r2
                     WHERE r2.user_id = resumes.user_id AND r2.is_active
                 );
            """)

            # resume_skills: per-résumé ATS extraction output
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resume_skills (
                    id         SERIAL PRIMARY KEY,
                    resume_id  INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                    skill      TEXT NOT NULL,
                    kind       TEXT NOT NULL DEFAULT 'hard',   -- 'hard' | 'soft'
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (resume_id, skill, kind)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS resume_skills_resume_idx ON resume_skills (resume_id);")

            # user_job_core: tier 1 — hard job-search restrictions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_job_core (
                    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    min_experience  INTEGER,
                    max_experience  INTEGER,
                    education_level  TEXT,   -- none|bootcamp|associate|bachelor|master|phd (semantic hint only)
                    updated_at      TIMESTAMP DEFAULT NOW()
                );
            """)

            # user_job_preferences: tier 2 — soft job-search filters
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_job_preferences (
                    user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    preferred_roles     TEXT[]  NOT NULL DEFAULT '{}',
                    preferred_locations TEXT[]  NOT NULL DEFAULT '{}',
                    preferred_seniority TEXT[]  NOT NULL DEFAULT '{}',
                    remote_only         BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at          TIMESTAMP DEFAULT NOW()
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

            # ── Pipeline stats ───────────────────────────────────────────────
            # Single-row table the ETL pipeline is the sole writer of — lets the
            # web app read a cheap, server-wide job count without ever
            # querying `jobs` itself (see refresh_job_count_stat / get_job_count_stat).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_stats (
                    id         SMALLINT PRIMARY KEY DEFAULT 1,
                    job_count  INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    CHECK (id = 1)
                );
            """)

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


def refresh_job_count_stat(conn) -> int:
    """Recompute and persist the total job count into `pipeline_stats`.
    Called only by the ETL pipeline after loading — the web app must never
    call this; it only reads the value via get_job_count_stat."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_stats (id, job_count, updated_at)
            VALUES (1, (SELECT COUNT(*) FROM jobs), NOW())
            ON CONFLICT (id) DO UPDATE
                SET job_count  = EXCLUDED.job_count,
                    updated_at = EXCLUDED.updated_at
            RETURNING job_count;
        """)
        count = cur.fetchone()[0]
    conn.commit()
    log.info("pipeline_stats.job_count refreshed to %d.", count)
    return count


def get_job_count_stat(conn) -> Optional[int]:
    """Read the ETL-maintained job count. None if the ETL has never run."""
    with conn.cursor() as cur:
        cur.execute("SELECT job_count FROM pipeline_stats WHERE id = 1")
        row = cur.fetchone()
    return row[0] if row else None


# Process-lifetime cache, shared by every agent prompt that needs the count
# (orchestrator, db_agent, ...) so it's read from Postgres at most once per
# server process rather than once per agent. The ETL is the only writer of
# the underlying value (refresh_job_count_stat); the web app just reflects
# whatever it last saw — a fresh number only ever appears after a restart.
_job_count_cache: Optional[int] = None
_job_count_loaded = False


def get_job_count_cached() -> str:
    """Cached, prompt-ready text form of the ETL-maintained job count."""
    global _job_count_cache, _job_count_loaded
    if not _job_count_loaded:
        try:
            conn = get_connection()
            try:
                _job_count_cache = get_job_count_stat(conn)
            finally:
                conn.close()
        except Exception:
            log.warning("Could not load pipeline_stats.job_count.", exc_info=True)
        _job_count_loaded = True
    return str(_job_count_cache) if _job_count_cache is not None else "unknown"


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