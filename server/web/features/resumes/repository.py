from typing import Optional, List
from server.db.postgres import get_connection


_RESUME_COLS = "id, user_id, title, filename, content, is_active, uploaded_at, updated_at"
_LIST_COLS = "id, title, filename, is_active, uploaded_at, updated_at"


def _row_to_dict(row, cols: str) -> dict:
    return dict(zip([c.strip() for c in cols.split(",")], row))


def next_resume_title(user_id: int, career_stage: Optional[str]) -> str:
    """System-generated résumé title, e.g. 'Working Professional Resume 2'."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM resumes WHERE user_id = %s", (user_id,))
            n = (cur.fetchone()[0] or 0) + 1
    finally:
        conn.close()

    if career_stage:
        label = career_stage.replace("_", " ").replace("-", " ").strip().title()
        return f"{label} Resume {n}"
    return f"Resume {n}"


def list_resumes(user_id: int) -> List[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_LIST_COLS},
                       (SELECT COUNT(*) FROM resume_skills rs WHERE rs.resume_id = resumes.id) AS skill_count
                FROM resumes
                WHERE user_id = %s
                ORDER BY uploaded_at DESC, id DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    finally:
        conn.close()
    return [dict(zip(cols, r)) for r in rows]


def get_resume(user_id: int, resume_id: Optional[int] = None) -> Optional[dict]:
    """Return one résumé for the user. With `resume_id`, that specific résumé
    (scoped to the user); otherwise the user's active résumé."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if resume_id is not None:
                cur.execute(
                    f"SELECT {_RESUME_COLS} FROM resumes WHERE user_id = %s AND id = %s",
                    (user_id, resume_id),
                )
            else:
                cur.execute(
                    f"SELECT {_RESUME_COLS} FROM resumes WHERE user_id = %s AND is_active "
                    f"ORDER BY uploaded_at DESC LIMIT 1",
                    (user_id,),
                )
            row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_dict(row, _RESUME_COLS) if row else None


def get_resume_skills(resume_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT skill, kind FROM resume_skills WHERE resume_id = %s ORDER BY id",
                (resume_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "skills": [r[0] for r in rows if r[1] == "hard"],
        "soft_skills": [r[0] for r in rows if r[1] == "soft"],
    }


def create_resume(user_id: int, filename: str, content: str, title: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO resumes (user_id, filename, content, title) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, filename, content, title),
            )
            resume_id = cur.fetchone()[0]
        conn.commit()
        return resume_id
    finally:
        conn.close()


def replace_resume_skills(resume_id: int, skills: List[str], soft_skills: List[str]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resume_skills WHERE resume_id = %s", (resume_id,))
            for skill in skills:
                cur.execute(
                    "INSERT INTO resume_skills (resume_id, skill, kind) VALUES (%s, %s, 'hard') "
                    "ON CONFLICT (resume_id, skill, kind) DO NOTHING",
                    (resume_id, skill),
                )
            for skill in soft_skills:
                cur.execute(
                    "INSERT INTO resume_skills (resume_id, skill, kind) VALUES (%s, %s, 'soft') "
                    "ON CONFLICT (resume_id, skill, kind) DO NOTHING",
                    (resume_id, skill),
                )
        conn.commit()
    finally:
        conn.close()


def set_active_resume(user_id: int, resume_id: int) -> None:
    # Two statements (clear then set) so the partial unique index
    # `resumes_one_active_per_user` is never transiently violated mid-UPDATE.
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE resumes SET is_active = FALSE WHERE user_id = %s AND is_active",
                (user_id,),
            )
            cur.execute(
                "UPDATE resumes SET is_active = TRUE, updated_at = NOW() "
                "WHERE user_id = %s AND id = %s",
                (user_id, resume_id),
            )
        conn.commit()
    finally:
        conn.close()


def rename_resume(user_id: int, resume_id: int, title: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE resumes SET title = %s, updated_at = NOW() WHERE user_id = %s AND id = %s",
                (title, user_id, resume_id),
            )
            changed = cur.rowcount > 0
        conn.commit()
        return changed
    finally:
        conn.close()


def delete_resume(user_id: int, resume_id: Optional[int] = None) -> bool:
    """Delete one résumé. With no `resume_id`, deletes the active one.
    If the deleted résumé was active, the newest remaining one is promoted."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if resume_id is None:
                cur.execute(
                    "SELECT id FROM resumes WHERE user_id = %s AND is_active LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                resume_id = row[0]

            cur.execute(
                "DELETE FROM resumes WHERE user_id = %s AND id = %s RETURNING is_active",
                (user_id, resume_id),
            )
            deleted = cur.fetchone()
            if not deleted:
                return False

            was_active = deleted[0]
            if was_active:
                cur.execute(
                    """
                    UPDATE resumes SET is_active = TRUE, updated_at = NOW()
                    WHERE id = (
                        SELECT id FROM resumes WHERE user_id = %s
                        ORDER BY uploaded_at DESC, id DESC LIMIT 1
                    )
                    """,
                    (user_id,),
                )
        conn.commit()
        return True
    finally:
        conn.close()
