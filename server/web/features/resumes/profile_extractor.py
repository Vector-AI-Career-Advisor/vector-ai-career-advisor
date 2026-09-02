import json
import os
import re
from typing import Any, Dict, List

import anthropic


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Could not parse JSON from AI profile extraction response")


def extract_profile_from_resume(resume_text: str) -> Dict[str, Any]:
    """Extract resume-driven profile fields with a strong, constrained JSON schema."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    prompt = f"""
You are extracting structured profile data from a resume. Return only valid JSON with this schema:

{
  "first_name": "string or null",
  "last_name": "string or null",
  "phone": "string or null",
  "city": "string or null",
  "years_experience": 0,
  "career_stage": "student|recent_graduate|working_professional|career_switcher|between_jobs|returning|null",
  "education": {
    "degree_type": "string or null",
    "field_of_study": "string or null",
    "school": "string or null",
    "graduation_year": 0
  },
  "skills": ["string"],
  "soft_skills": ["string"],
  "work_experience": [
    {"position": "string or null", "company": "string or null", "start_date": "YYYY-MM-DD or null", "end_date": "YYYY-MM-DD or null"}
  ]
}

RULES:
- Only use facts that are actually in the resume.
- Keep skill names short and standardized.
- Do not invent employers, dates, or schools.
- If a field is not found, use null or [] as appropriate.
- Deduplicate skills and soft skills.
- Limit work_experience to up to 3 entries.
- Keep output valid JSON only, no markdown.

RESUME:
{resume_text[:8000]}
"""

    try:
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet") ,
            max_tokens=1000,
            system="Extract profile data from a resume into valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        payload = _parse_json_response(response.content[0].text)
    except Exception:
        payload = {
            "first_name": None,
            "last_name": None,
            "phone": None,
            "city": None,
            "years_experience": 0,
            "career_stage": None,
            "education": {"degree_type": None, "field_of_study": None, "school": None, "graduation_year": 0},
            "skills": [],
            "soft_skills": [],
            "work_experience": [],
        }

    return {
        "first_name": _clean(payload.get("first_name")),
        "last_name": _clean(payload.get("last_name")),
        "phone": _clean(payload.get("phone")) or None,
        "city": _clean(payload.get("city")) or None,
        "years_experience": int(payload.get("years_experience") or 0),
        "career_stage": payload.get("career_stage") or None,
        "education": {
            "degree_type": _clean(payload.get("education", {}).get("degree_type")) or None,
            "field_of_study": _clean(payload.get("education", {}).get("field_of_study")) or None,
            "school": _clean(payload.get("education", {}).get("school")) or None,
            "graduation_year": int((payload.get("education", {}) or {}).get("graduation_year") or 0) or 0,
        },
        "skills": [
            _clean(s)
            for s in (payload.get("skills") or [])
            if _clean(s)
        ][:20],
        "soft_skills": [
            _clean(s)
            for s in (payload.get("soft_skills") or [])
            if _clean(s)
        ][:12],
        "work_experience": payload.get("work_experience") or [],
    }
