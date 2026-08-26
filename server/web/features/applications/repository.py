from typing import List, Optional
from server.db.postgres import get_connection, fetch_applications_by_user, add_application, update_application_status


def get_applications(user_id: int, status: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    try:
        return fetch_applications_by_user(conn, user_id, status)
    finally:
        conn.close()


def create_application(user_id: int, job_id: str) -> dict:
    conn = get_connection()
    try:
        return add_application(conn, user_id, job_id)
    except Exception as e:
        if getattr(e, "pgcode", None) == "23505":
            raise ValueError("already_applied")
        raise
    finally:
        conn.close()


def patch_status(user_id: int, job_id: str, status: str) -> dict:
    conn = get_connection()
    try:
        return update_application_status(conn, user_id, job_id, status)
    finally:
        conn.close()
