import io
import logging
import zipfile
from xml.etree import ElementTree as ET

from fastapi import HTTPException, UploadFile
import pypdf
from features.resumes import repository
from features.resumes.profile_extractor import extract_profile_from_resume
from server.db.postgres import get_connection

log = logging.getLogger(__name__)


def _extract_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def _extract_text_from_docx(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = [node.text or "" for node in root.findall(".//w:t", ns)]
    return "\n".join(paragraphs).strip()


async def upload_resume(user_id: int, file: UploadFile) -> dict:
    filename = (file.filename or "").lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        log.warning("Resume upload rejected for user %s — unsupported format: %s", user_id, file.filename)
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are accepted")

    contents = await file.read()
    if filename.endswith(".pdf"):
        text = _extract_text(contents)
        kind = "PDF"
    else:
        text = _extract_text_from_docx(contents)
        kind = "DOCX"

    if not text:
        log.warning("Resume upload rejected for user %s — no extractable text: %s", user_id, file.filename)
        raise HTTPException(status_code=400, detail=f"Could not extract text from {kind}")

    repository.save_resume(user_id, file.filename, text)

    try:
        extracted = extract_profile_from_resume(text)
        conn = get_connection()
        with conn.cursor() as cur:
            if extracted.get("first_name") or extracted.get("last_name"):
                cur.execute(
                    "UPDATE users SET first_name = COALESCE(%s, first_name), last_name = COALESCE(%s, last_name), phone = COALESCE(%s, phone), city = COALESCE(%s, city), years_experience = COALESCE(CAST(%s AS INTEGER), years_experience), career_stage = COALESCE(%s, career_stage), updated_at = NOW() WHERE id = %s",
                    (
                        extracted.get("first_name"),
                        extracted.get("last_name"),
                        extracted.get("phone"),
                        extracted.get("city"),
                        extracted.get("years_experience"),
                        extracted.get("career_stage"),
                        user_id,
                    ),
                )

            edu = extracted.get("education") or {}
            if edu.get("degree_type") or edu.get("field_of_study") or edu.get("school"):
                cur.execute(
                    """
                    INSERT INTO user_educations (user_id, degree_type, field_of_study, school, graduation_year)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        user_id,
                        edu.get("degree_type"),
                        edu.get("field_of_study"),
                        edu.get("school"),
                        edu.get("graduation_year") or None,
                    ),
                )

            for skill in extracted.get("skills") or []:
                cur.execute(
                    "INSERT INTO user_skills (user_id, skill, category) VALUES (%s, %s, %s) ON CONFLICT (user_id, skill) DO NOTHING",
                    (user_id, skill, "resume"),
                )

            for skill in extracted.get("soft_skills") or []:
                cur.execute(
                    "INSERT INTO user_soft_skills (user_id, skill) VALUES (%s, %s) ON CONFLICT (user_id, skill) DO NOTHING",
                    (user_id, skill),
                )

            for exp in extracted.get("work_experience") or []:
                cur.execute(
                    """
                    INSERT INTO user_work_experience (user_id, position, company, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        user_id,
                        exp.get("position"),
                        exp.get("company"),
                        exp.get("start_date"),
                        exp.get("end_date"),
                    ),
                )
        conn.commit()
    except Exception as exc:
        log.warning("Resume-derived profile extraction failed for user %s: %s", user_id, exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    log.info("Resume uploaded for user %s: %s", user_id, file.filename)
    return {"message": "Resume uploaded successfully", "filename": file.filename}


def get_my_resume(user_id: int) -> dict:
    resume = repository.get_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume on file")
    return resume


def delete_my_resume(user_id: int) -> None:
    repository.delete_resume(user_id)
