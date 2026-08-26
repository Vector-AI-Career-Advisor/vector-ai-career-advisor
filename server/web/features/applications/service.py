from typing import List, Optional
from server.web.features.applications import repository


def list_applications(user_id: int, status: Optional[str] = None) -> List[dict]:
    return repository.get_applications(user_id, status)


def create_application(user_id: int, job_id: str) -> dict:
    return repository.create_application(user_id, job_id)


def update_status(user_id: int, job_id: str, status: str) -> dict:
    return repository.patch_status(user_id, job_id, status)
