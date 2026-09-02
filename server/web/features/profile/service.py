import json
import logging
from typing import Optional, List, Dict
from fastapi import HTTPException
from server.db.postgres import get_connection
from server.web.features.profile.schemas import (
    BasicInfoRequest, CareerStageRequest, EducationRequest, SkillRequest,
    SoftSkillRequest, LanguageRequest, WorkExperienceRequest, CertificationRequest,
    VolunteeringRequest, ClubOrgRequest, PreferencesRequest
)

log = logging.getLogger(__name__)


def update_basic_info(user_id: int, data: BasicInfoRequest) -> dict:
    """Update user basic information."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET first_name = %s, last_name = %s, phone = %s, city = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id, email, first_name, last_name, phone, city, years_experience, career_stage, created_at, updated_at;
            """, (data.first_name, data.last_name, data.phone, data.city, user_id))
            row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Updated basic info for user %d", user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def update_career_stage(user_id: int, data: CareerStageRequest) -> dict:
    """Update user career stage and years of experience."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET career_stage = %s, years_experience = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id, email, first_name, last_name, phone, city, years_experience, career_stage, created_at, updated_at;
            """, (data.career_stage, data.years_experience, user_id))
            row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Updated career stage for user %d", user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def add_education(user_id: int, data: EducationRequest) -> dict:
    """Add education entry."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_educations (user_id, degree_type, field_of_study, school, graduation_year, relevant_courses, academic_highlights)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, degree_type, field_of_study, school, graduation_year, relevant_courses, academic_highlights, created_at;
            """, (user_id, data.degree_type, data.field_of_study, data.school, data.graduation_year, data.relevant_courses, data.academic_highlights))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Added education for user %d", user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_education(user_id: int) -> List[dict]:
    """Get all education entries for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, degree_type, field_of_study, school, graduation_year, relevant_courses, academic_highlights, created_at
                FROM user_educations
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()

        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def update_education(user_id: int, education_id: int, data: EducationRequest) -> dict:
    """Update an education entry the user owns."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_educations
                SET degree_type = %s, field_of_study = %s, school = %s, graduation_year = %s,
                    relevant_courses = %s, academic_highlights = %s
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, degree_type, field_of_study, school, graduation_year, relevant_courses, academic_highlights, created_at;
            """, (data.degree_type, data.field_of_study, data.school, data.graduation_year,
                  data.relevant_courses, data.academic_highlights, education_id, user_id))
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
        if row is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Education entry not found")
        conn.commit()
        log.info("Updated education %d for user %d", education_id, user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def delete_education(user_id: int, education_id: int) -> bool:
    """Delete an education entry the user owns."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_educations WHERE id = %s AND user_id = %s;", (education_id, user_id))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def add_skill(user_id: int, data: SkillRequest) -> dict:
    """Add a technical skill."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_skills (user_id, skill, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, skill) DO UPDATE SET skill = EXCLUDED.skill
                RETURNING id, user_id, skill, category, created_at;
            """, (user_id, data.skill, data.category))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Added skill '%s' for user %d", data.skill, user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_skills(user_id: int) -> List[dict]:
    """Get all technical skills for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, skill, category, created_at
                FROM user_skills
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
        
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def delete_skill(user_id: int, skill_id: int) -> bool:
    """Delete a skill."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_skills WHERE id = %s AND user_id = %s;
            """, (skill_id, user_id))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def add_soft_skill(user_id: int, data: SoftSkillRequest) -> dict:
    """Add a soft skill."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_soft_skills (user_id, skill)
                VALUES (%s, %s)
                ON CONFLICT (user_id, skill) DO UPDATE SET skill = EXCLUDED.skill
                RETURNING id, user_id, skill, created_at;
            """, (user_id, data.skill))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_soft_skills(user_id: int) -> List[dict]:
    """Get all soft skills for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, skill, created_at
                FROM user_soft_skills
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
        
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def add_language(user_id: int, data: LanguageRequest) -> dict:
    """Add a language."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_languages (user_id, language, proficiency)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, language) DO UPDATE SET proficiency = EXCLUDED.proficiency
                RETURNING id, user_id, language, proficiency, created_at;
            """, (user_id, data.language, data.proficiency))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_languages(user_id: int) -> List[dict]:
    """Get all languages for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, language, proficiency, created_at
                FROM user_languages
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
        
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def add_work_experience(user_id: int, data: WorkExperienceRequest) -> dict:
    """Add work experience."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_work_experience (user_id, position, company, start_date, end_date, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, position, company, start_date, end_date, description, created_at;
            """, (user_id, data.position, data.company, data.start_date, data.end_date, data.description))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Added work experience for user %d", user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_work_experience(user_id: int) -> List[dict]:
    """Get all work experience for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, position, company, start_date, end_date, description, created_at
                FROM user_work_experience
                WHERE user_id = %s
                ORDER BY start_date DESC NULLS LAST, created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()

        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def update_work_experience(user_id: int, experience_id: int, data: WorkExperienceRequest) -> dict:
    """Update a work-experience entry the user owns."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_work_experience
                SET position = %s, company = %s, start_date = %s, end_date = %s, description = %s
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, position, company, start_date, end_date, description, created_at;
            """, (data.position, data.company, data.start_date, data.end_date, data.description,
                  experience_id, user_id))
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
        if row is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Work experience entry not found")
        conn.commit()
        log.info("Updated work experience %d for user %d", experience_id, user_id)
        return dict(zip(cols, row))
    finally:
        conn.close()


def delete_work_experience(user_id: int, experience_id: int) -> bool:
    """Delete a work-experience entry the user owns."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_work_experience WHERE id = %s AND user_id = %s;", (experience_id, user_id))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def add_certification(user_id: int, data: CertificationRequest) -> dict:
    """Add a certification."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_certifications (user_id, certification, issuer, date_obtained)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, certification, issuer, date_obtained, created_at;
            """, (user_id, data.certification, data.issuer, data.date_obtained))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_certifications(user_id: int) -> List[dict]:
    """Get all certifications for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, certification, issuer, date_obtained, created_at
                FROM user_certifications
                WHERE user_id = %s
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cur.fetchall()
        
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def add_volunteering(user_id: int, data: VolunteeringRequest) -> dict:
    """Add volunteering experience."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_volunteering (user_id, role, organization, start_date, end_date, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, role, organization, start_date, end_date, description, created_at;
            """, (user_id, data.role, data.organization, data.start_date, data.end_date, data.description))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return dict(zip(cols, row))
    finally:
        conn.close()


def add_club_org(user_id: int, data: ClubOrgRequest) -> dict:
    """Add club or organization membership."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_clubs_orgs (user_id, name, role)
                VALUES (%s, %s, %s)
                RETURNING id, user_id, name, role, created_at;
            """, (user_id, data.name, data.role))
            row = cur.fetchone()
        
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return dict(zip(cols, row))
    finally:
        conn.close()


def update_preferences(user_id: int, data: PreferencesRequest) -> dict:
    """Update or create user preferences."""
    conn = get_connection()
    try:
        work_preferences = json.dumps(data.work_preferences) if data.work_preferences is not None else None
        interests = json.dumps(data.interests) if data.interests is not None else None

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_preferences (user_id, github_url, portfolio_url, work_preferences, interests)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                ON CONFLICT (user_id) DO UPDATE SET
                    github_url = COALESCE(EXCLUDED.github_url, user_preferences.github_url),
                    portfolio_url = COALESCE(EXCLUDED.portfolio_url, user_preferences.portfolio_url),
                    work_preferences = COALESCE(EXCLUDED.work_preferences, user_preferences.work_preferences),
                    interests = COALESCE(EXCLUDED.interests, user_preferences.interests),
                    updated_at = NOW()
                RETURNING id, user_id, github_url, portfolio_url, work_preferences, interests, created_at, updated_at;
            """, (user_id, data.github_url, data.portfolio_url, work_preferences, interests))
            row = cur.fetchone()

        if row is None:
            cur.execute("""
                SELECT id, user_id, github_url, portfolio_url, work_preferences, interests, created_at, updated_at
                FROM user_preferences
                WHERE user_id = %s;
            """, (user_id,))
            row = cur.fetchone()

        cols = [desc[0] for desc in cur.description]
        conn.commit()
        log.info("Updated preferences for user %d", user_id)
        return dict(zip(cols, row)) if row else {}
    finally:
        conn.close()


def get_profile(user_id: int) -> Optional[dict]:
    """Get complete user profile including basic info."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, email, first_name, last_name, phone, city, years_experience, career_stage, created_at, updated_at
                FROM users
                WHERE id = %s;
            """, (user_id,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_profile_summary(user_id: int) -> dict:
    """Return the current user profile summary for the profile page and job filters."""
    profile = get_profile(user_id) or {}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT degree_type, field_of_study, school, graduation_year
                FROM user_educations
                WHERE user_id = %s
                ORDER BY graduation_year DESC NULLS LAST, created_at DESC
                LIMIT 1;
            """, (user_id,))
            education = cur.fetchone()

            cur.execute("""
                SELECT skill
                FROM user_skills
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 12;
            """, (user_id,))
            skills = [row[0] for row in cur.fetchall()]

            cur.execute("""
                SELECT skill
                FROM user_soft_skills
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 10;
            """, (user_id,))
            soft_skills = [row[0] for row in cur.fetchall()]

            cur.execute("""
                SELECT position, company, start_date, end_date
                FROM user_work_experience
                WHERE user_id = %s
                ORDER BY start_date DESC NULLS LAST, created_at DESC
                LIMIT 3;
            """, (user_id,))
            work_experience = [
                {
                    "position": row[0],
                    "company": row[1],
                    "start_date": row[2],
                    "end_date": row[3],
                }
                for row in cur.fetchall()
            ]

            cur.execute("""
                SELECT work_preferences
                FROM user_preferences
                WHERE user_id = %s;
            """, (user_id,))
            prefs_row = cur.fetchone()
            work_preferences = prefs_row[0] if prefs_row and prefs_row[0] else {}
    finally:
        conn.close()

    education_summary = {}
    if education:
        education_summary = {
            "degree_type": education[0],
            "field_of_study": education[1],
            "school": education[2],
            "graduation_year": education[3],
        }

    derived_filters = {
        "keyword": " ".join(skills[:3]),
        "skills": skills[:8],
        "location": profile.get("city"),
        "years_experience_min": profile.get("years_experience"),
        "seniority": profile.get("career_stage"),
        "work_preferences": work_preferences,
    }

    return {
        "user": {
            "id": profile.get("id"),
            "email": profile.get("email"),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "phone": profile.get("phone"),
            "city": profile.get("city"),
            "years_experience": profile.get("years_experience"),
            "career_stage": profile.get("career_stage"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
        },
        "education": education_summary,
        "skills": skills,
        "soft_skills": soft_skills,
        "work_experience": work_experience,
        "work_preferences": work_preferences,
        "job_filters": derived_filters,
    }


def check_onboarding_complete(user_id: int) -> bool:
    """Check if user has completed basic onboarding (at minimum)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM users 
                WHERE id = %s AND first_name IS NOT NULL AND last_name IS NOT NULL 
                AND years_experience IS NOT NULL AND career_stage IS NOT NULL;
            """, (user_id,))
            row = cur.fetchone()
        return row[0] > 0 if row else False
    finally:
        conn.close()
