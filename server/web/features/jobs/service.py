from typing import Optional, List
from features.jobs import repository


def list_jobs(
    keyword: Optional[str] = None,
    seniority: Optional[str] = None,
    location: Optional[str] = None,
    posted_date: Optional[str] = None,
    roles: Optional[List[str]] = None,
    years_experience_min: Optional[int] = None,
    skills: Optional[List[str]] = None,
    limit: int = repository.LIMIT,
    offset: int = 0,
) -> dict:
    return repository.list_jobs(
        keyword,
        seniority,
        location,
        posted_date,
        roles,
        years_experience_min,
        skills,
        limit,
        offset,
    )


def get_job(job_id: str) -> Optional[dict]:
    return repository.get_job(job_id)
