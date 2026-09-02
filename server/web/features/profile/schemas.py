from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime


class BasicInfoRequest(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None


class CareerStageRequest(BaseModel):
    career_stage: str  # "student", "recent_graduate", "working_professional", "career_switcher", "between_jobs", "returning"
    years_experience: int


class EducationRequest(BaseModel):
    degree_type: str  # "bachelor", "master", "phd", "bootcamp", "self-taught", "other"
    field_of_study: str
    school: str
    graduation_year: int
    relevant_courses: Optional[str] = None
    academic_highlights: Optional[str] = None


class SkillRequest(BaseModel):
    skill: str
    category: Optional[str] = None


class SoftSkillRequest(BaseModel):
    skill: str


class LanguageRequest(BaseModel):
    language: str
    proficiency: Optional[str] = None  # "beginner", "intermediate", "fluent", "native"


class WorkExperienceRequest(BaseModel):
    position: str
    company: str
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = None


class CertificationRequest(BaseModel):
    certification: str
    issuer: Optional[str] = None
    date_obtained: Optional[date] = None


class VolunteeringRequest(BaseModel):
    role: str
    organization: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class ClubOrgRequest(BaseModel):
    name: str
    role: Optional[str] = None


class PreferencesRequest(BaseModel):
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    work_preferences: Optional[dict] = None  # {"building_products": True, "data_insights": True, ...}
    interests: Optional[List[str]] = None


class ProfileResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    city: Optional[str]
    years_experience: Optional[int]
    career_stage: Optional[str]
    created_at: datetime
    updated_at: datetime


class OnboardingStatusResponse(BaseModel):
    completed: bool
    steps_completed: List[str]  # List of completed step names
    current_step: Optional[str] = None
