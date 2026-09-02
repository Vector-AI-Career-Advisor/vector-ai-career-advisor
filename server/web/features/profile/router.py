from fastapi import APIRouter, Depends, HTTPException
from core.security import get_current_user
from features.profile import service
from features.profile.schemas import (
    BasicInfoRequest, CareerStageRequest, EducationRequest, SkillRequest,
    SoftSkillRequest, LanguageRequest, WorkExperienceRequest, CertificationRequest,
    VolunteeringRequest, ClubOrgRequest, PreferencesRequest, OnboardingStatusResponse
)

router = APIRouter()


# ── Basic Info ──────────────────────────────────────────────────────────────

@router.post("/basic-info")
def update_basic_info(data: BasicInfoRequest, user_id: str = Depends(get_current_user)):
    return service.update_basic_info(int(user_id), data)


@router.post("/career-stage")
def update_career_stage(data: CareerStageRequest, user_id: str = Depends(get_current_user)):
    return service.update_career_stage(int(user_id), data)


# ── Education ────────────────────────────────────────────────────────────────

@router.post("/education")
def add_education(data: EducationRequest, user_id: str = Depends(get_current_user)):
    return service.add_education(int(user_id), data)


@router.get("/education")
def get_education(user_id: str = Depends(get_current_user)):
    return service.get_education(int(user_id))


# ── Technical Skills ────────────────────────────────────────────────────────

@router.post("/skills")
def add_skill(data: SkillRequest, user_id: str = Depends(get_current_user)):
    return service.add_skill(int(user_id), data)


@router.get("/skills")
def get_skills(user_id: str = Depends(get_current_user)):
    return service.get_skills(int(user_id))


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, user_id: str = Depends(get_current_user)):
    success = service.delete_skill(int(user_id), skill_id)
    return {"success": success}


# ── Soft Skills ──────────────────────────────────────────────────────────────

@router.post("/soft-skills")
def add_soft_skill(data: SoftSkillRequest, user_id: str = Depends(get_current_user)):
    return service.add_soft_skill(int(user_id), data)


@router.get("/soft-skills")
def get_soft_skills(user_id: str = Depends(get_current_user)):
    return service.get_soft_skills(int(user_id))


# ── Languages ────────────────────────────────────────────────────────────────

@router.post("/languages")
def add_language(data: LanguageRequest, user_id: str = Depends(get_current_user)):
    return service.add_language(int(user_id), data)


@router.get("/languages")
def get_languages(user_id: str = Depends(get_current_user)):
    return service.get_languages(int(user_id))


# ── Work Experience ──────────────────────────────────────────────────────────

@router.post("/work-experience")
def add_work_experience(data: WorkExperienceRequest, user_id: str = Depends(get_current_user)):
    return service.add_work_experience(int(user_id), data)


@router.get("/work-experience")
def get_work_experience(user_id: str = Depends(get_current_user)):
    return service.get_work_experience(int(user_id))


# ── Certifications ───────────────────────────────────────────────────────────

@router.post("/certifications")
def add_certification(data: CertificationRequest, user_id: str = Depends(get_current_user)):
    return service.add_certification(int(user_id), data)


@router.get("/certifications")
def get_certifications(user_id: str = Depends(get_current_user)):
    return service.get_certifications(int(user_id))


# ── Volunteering ────────────────────────────────────────────────────────────

@router.post("/volunteering")
def add_volunteering(data: VolunteeringRequest, user_id: str = Depends(get_current_user)):
    return service.add_volunteering(int(user_id), data)


# ── Clubs & Organizations ───────────────────────────────────────────────────

@router.post("/clubs-orgs")
def add_club_org(data: ClubOrgRequest, user_id: str = Depends(get_current_user)):
    return service.add_club_org(int(user_id), data)


# ── Preferences ──────────────────────────────────────────────────────────────

@router.post("/preferences")
def update_preferences(data: PreferencesRequest, user_id: str = Depends(get_current_user)):
    return service.update_preferences(int(user_id), data)


# ── Complete Profile ────────────────────────────────────────────────────────

@router.get("/me")
def get_profile(user_id: str = Depends(get_current_user)):
    profile = service.get_profile(int(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/summary")
def get_profile_summary(user_id: str = Depends(get_current_user)):
    summary = service.get_profile_summary(int(user_id))
    if not summary.get("user"):
        raise HTTPException(status_code=404, detail="Profile not found")
    return summary


@router.get("/onboarding-status", response_model=OnboardingStatusResponse)
def get_onboarding_status(user_id: str = Depends(get_current_user)):
    """Check if user has completed onboarding."""
    completed = service.check_onboarding_complete(int(user_id))
    return OnboardingStatusResponse(
        completed=completed,
        steps_completed=["basic-info", "career-stage"] if completed else []
    )
