"""Tier 1/2/3 job-search profile: core restrictions, soft preferences, résumé skills.

Consumed by the `find_jobs_for_me` agent tool and the deterministic
`/agents/login-recommendation` endpoint.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from server.db.postgres import get_connection

log = logging.getLogger(__name__)


# ── CRUD: tier 1 (core) ──────────────────────────────────────────────────────

_CORE_DEFAULT = {"min_experience": None, "max_experience": None, "education_level": None}


def get_job_core(user_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT min_experience, max_experience, education_level "
                "FROM user_job_core WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return dict(_CORE_DEFAULT)
    return {"min_experience": row[0], "max_experience": row[1], "education_level": row[2]}


def update_job_core(user_id: int, data: dict) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_job_core (user_id, min_experience, max_experience, education_level)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    min_experience = EXCLUDED.min_experience,
                    max_experience = EXCLUDED.max_experience,
                    education_level = EXCLUDED.education_level,
                    updated_at = NOW()
                """,
                (
                    user_id,
                    data.get("min_experience"),
                    data.get("max_experience"),
                    data.get("education_level"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return get_job_core(user_id)


# ── CRUD: tier 2 (preferences) ───────────────────────────────────────────────

_PREF_DEFAULT = {
    "preferred_roles": [],
    "preferred_locations": [],
    "preferred_seniority": [],
    "remote_only": False,
}


def get_job_preferences(user_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT preferred_roles, preferred_locations, preferred_seniority, remote_only "
                "FROM user_job_preferences WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _PREF_DEFAULT.items()}
    return {
        "preferred_roles": list(row[0] or []),
        "preferred_locations": list(row[1] or []),
        "preferred_seniority": list(row[2] or []),
        "remote_only": bool(row[3]),
    }


def update_job_preferences(user_id: int, data: dict) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_job_preferences
                    (user_id, preferred_roles, preferred_locations, preferred_seniority, remote_only)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    preferred_roles = EXCLUDED.preferred_roles,
                    preferred_locations = EXCLUDED.preferred_locations,
                    preferred_seniority = EXCLUDED.preferred_seniority,
                    remote_only = EXCLUDED.remote_only,
                    updated_at = NOW()
                """,
                (
                    user_id,
                    list(data.get("preferred_roles") or []),
                    list(data.get("preferred_locations") or []),
                    list(data.get("preferred_seniority") or []),
                    bool(data.get("remote_only", False)),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return get_job_preferences(user_id)


# ── Aggregate ────────────────────────────────────────────────────────────────

def build_job_search_profile(user_id: int) -> dict:
    """The single aggregator: core + preferences + active-résumé skills + education."""
    core = get_job_core(user_id)
    preferences = get_job_preferences(user_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT career_stage FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            career_stage = row[0] if row else None

            cur.execute(
                "SELECT id FROM resumes WHERE user_id = %s "
                "ORDER BY is_active DESC, uploaded_at DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            active_resume_id = row[0] if row else None

            skills: List[str] = []
            soft_skills: List[str] = []
            if active_resume_id is not None:
                cur.execute(
                    "SELECT skill, kind FROM resume_skills WHERE resume_id = %s ORDER BY id",
                    (active_resume_id,),
                )
                for skill, kind in cur.fetchall():
                    (soft_skills if kind == "soft" else skills).append(skill)

            cur.execute("SELECT skill FROM user_skills WHERE user_id = %s", (user_id,))
            skills += [r[0] for r in cur.fetchall()]
            cur.execute("SELECT skill FROM user_soft_skills WHERE user_id = %s", (user_id,))
            soft_skills += [r[0] for r in cur.fetchall()]

            cur.execute(
                """
                SELECT degree_type, field_of_study, school, graduation_year
                FROM user_educations WHERE user_id = %s
                ORDER BY graduation_year DESC NULLS LAST, created_at DESC LIMIT 1
                """,
                (user_id,),
            )
            edu_row = cur.fetchone()
    finally:
        conn.close()

    education = {}
    if edu_row:
        education = {
            "degree_type": edu_row[0],
            "field_of_study": edu_row[1],
            "school": edu_row[2],
            "graduation_year": edu_row[3],
        }

    return {
        "core": core,
        "preferences": preferences,
        "skills": _dedupe(skills),
        "soft_skills": _dedupe(soft_skills),
        "education": education,
        "career_stage": career_stage,
        "active_resume_id": active_resume_id,
    }


def has_signal(profile: dict) -> bool:
    return bool(
        profile.get("skills")
        or profile.get("preferences", {}).get("preferred_roles")
        or profile.get("preferences", {}).get("preferred_locations")
    )


def query_text(profile: dict) -> str:
    """Semantic query string built from preferred roles + résumé skills + field of study."""
    parts: List[str] = []
    parts += profile.get("preferences", {}).get("preferred_roles", [])
    parts += profile.get("skills", [])
    fos = (profile.get("education") or {}).get("field_of_study")
    if fos:
        parts.append(fos)
    return ", ".join(p for p in parts if p) or " "


def summarize_for_prompt(profile: dict) -> str:
    core = profile.get("core", {})
    prefs = profile.get("preferences", {})
    bits: List[str] = []
    if prefs.get("preferred_roles"):
        bits.append("preferred roles: " + ", ".join(prefs["preferred_roles"]))
    if prefs.get("preferred_locations"):
        bits.append("preferred locations: " + ", ".join(prefs["preferred_locations"]))
    if prefs.get("preferred_seniority"):
        bits.append("preferred seniority: " + ", ".join(prefs["preferred_seniority"]))
    if prefs.get("remote_only"):
        bits.append("remote only")
    if core.get("min_experience") is not None or core.get("max_experience") is not None:
        lo = core.get("min_experience")
        hi = core.get("max_experience")
        bits.append(f"required experience: {lo if lo is not None else 0}–{hi if hi is not None else '∞'} yrs")
    if core.get("education_level"):
        bits.append("education: " + core["education_level"])
    if profile.get("skills"):
        bits.append("skills: " + ", ".join(profile["skills"][:15]))
    return "; ".join(bits) if bits else "no saved job profile"


# ── Filters / ranking over ChromaDB hit metadata ─────────────────────────────

def _job_years(meta: dict) -> Optional[int]:
    raw = meta.get("yearsexperience", "")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def matches_core(meta: dict, core: dict) -> bool:
    """Hard gate. Jobs with no experience value always pass."""
    ye = _job_years(meta)
    if ye is None:
        return True
    lo = core.get("min_experience")
    hi = core.get("max_experience")
    if lo is not None and ye < lo:
        return False
    if hi is not None and ye > hi:
        return False
    return True


def _pref_match(meta: dict, prefs: dict) -> bool:
    location = (meta.get("location") or "").lower()
    seniority = (meta.get("seniority") or "").lower()

    locs = [l.lower() for l in prefs.get("preferred_locations", []) if l]
    if prefs.get("remote_only"):
        if "remote" not in location:
            return False
    elif locs and not any(l in location or location in l for l in locs):
        return False

    sens = [s.lower() for s in prefs.get("preferred_seniority", []) if s]
    if sens and not any(s in seniority or seniority in s for s in sens):
        return False
    return True


def apply_preferences(hits: list, prefs: dict, want_n: int) -> list:
    """Soft filter with auto-relax: if fewer than `want_n` hits match, keep them all."""
    if not (prefs.get("preferred_locations") or prefs.get("preferred_seniority") or prefs.get("remote_only")):
        return hits
    filtered = [h for h in hits if _pref_match(h.get("metadata", {}), prefs)]
    return filtered if len(filtered) >= want_n else hits


def skill_rank(meta: dict, skills: list) -> int:
    if not skills:
        return 0
    haystack = ((meta.get("skills_must") or "") + ", " + (meta.get("skills_nice") or "")).lower()
    return sum(1 for s in skills if s and s.lower() in haystack)


# ── util ─────────────────────────────────────────────────────────────────────

def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        key = (it or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip())
    return out
