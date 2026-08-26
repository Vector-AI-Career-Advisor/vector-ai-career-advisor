from typing import Optional
from server.db.postgres import get_connection


def save_resume(user_id: int, filename: str, content: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resumes (user_id, filename, content)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET filename    = EXCLUDED.filename,
                        content     = EXCLUDED.content,
                        updated_at  = NOW()
                """,
                (user_id, filename, content),
            )
        conn.commit()
    finally:
        conn.close()


def get_resume(user_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, content, uploaded_at, updated_at FROM resumes WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {
        "filename":    row[0],
        "content":     row[1],
        "uploaded_at": row[2],
        "updated_at":  row[3],
    }


def delete_resume(user_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resumes WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()
