from typing import List

from server.db.postgres import (
    get_connection,
    upsert_saved_filter,
    fetch_saved_filters,
    delete_saved_filter,
)


def list_for_user(user_id: int) -> List[dict]:
    conn = get_connection()
    try:
        return fetch_saved_filters(conn, user_id)
    finally:
        conn.close()


def create(user_id: int, name: str, filters: dict) -> dict:
    conn = get_connection()
    try:
        return upsert_saved_filter(conn, user_id, name, filters)
    finally:
        conn.close()


def remove(user_id: int, filter_id: int) -> bool:
    conn = get_connection()
    try:
        return delete_saved_filter(conn, user_id, filter_id)
    finally:
        conn.close()
