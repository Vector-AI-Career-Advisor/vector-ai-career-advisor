from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FilterPayload(BaseModel):
    """The subset of job-search filters that defines a saved filter.
    Mirrors the client's JobFilters (minus pagination)."""
    keyword: Optional[str] = None
    seniority: Optional[str] = None
    location: Optional[str] = None
    posted_date: Optional[str] = None
    roles: Optional[List[str]] = None
    years_experience_min: Optional[int] = None
    years_experience_max: Optional[int] = None
    skills: Optional[List[str]] = None
    education: Optional[List[str]] = None

    model_config = {"extra": "ignore"}


class SavedFilterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: FilterPayload


class SavedFilterOut(BaseModel):
    id: int
    name: str
    # Echoed back exactly as stored (only the keys the user actually set).
    filters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
