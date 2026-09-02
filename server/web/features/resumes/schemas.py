from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ResumeOut(BaseModel):
    filename: str
    content: str
    uploaded_at: Optional[datetime]
    updated_at: Optional[datetime]


class ResumeListItem(BaseModel):
    id: int
    title: Optional[str]
    filename: str
    is_active: bool
    skill_count: int = 0
    uploaded_at: Optional[datetime]
    updated_at: Optional[datetime]


class ResumeDetail(BaseModel):
    id: int
    title: Optional[str]
    filename: str
    content: str
    is_active: bool
    skills: List[str] = []
    soft_skills: List[str] = []
    uploaded_at: Optional[datetime]
    updated_at: Optional[datetime]


class ResumeUpdateRequest(BaseModel):
    title: Optional[str] = None
    is_active: Optional[bool] = None
