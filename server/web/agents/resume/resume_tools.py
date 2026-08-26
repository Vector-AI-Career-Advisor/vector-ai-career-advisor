"""Resume Tools — upload, fetch, and tailor resume tools for the Resume Agent."""
from __future__ import annotations

import io
import os
import re
import textwrap

import anthropic
import psycopg2.extras
import pypdf
from langchain.tools import tool
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from server.db import get_connection

# Shared user context — set once at startup via set_current_user().
# Imported by agent.py (main entry point) so all tool modules share the same dict.
_context: dict = {"user_id": None}


def set_current_user(user_id: int) -> None:
    _context["user_id"] = user_id


# ── helpers ───────────────────────────────────────────────────────────────

def _conn():
    return get_connection()


def _save_pdf(text: str, filepath: str) -> None:
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_LEFT
    )
    header = ParagraphStyle(
        "header",
        parent=styles["Normal"],
        fontSize=12,
        leading=16,
        spaceAfter=2 * mm,
        fontName="Helvetica-Bold",
    )

    story = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 4 * mm))
            continue
        is_heading = (stripped.isupper() and len(stripped) < 60) or (
            stripped.endswith(":") and len(stripped) < 50
        )
        style = header if is_heading else body
        story.append(Paragraph(stripped, style))
        story.append(Spacer(1, 1 * mm))

    doc.build(story)


# ── tools ─────────────────────────────────────────────────────────────────

@tool
def upload_resume(path: str) -> dict:
    """Ingest a PDF resume from a local file path and store it for the current user.
    Use when the user wants to upload or replace their resume on file.
    - path: absolute or ~/... path to the PDF file
    """
    user_id = _context.get("user_id")
    if not user_id:
        return {"error": "No user session active. Sign in before uploading a resume."}

    path = os.path.expanduser(path.strip())
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}
    if not path.lower().endswith(".pdf"):
        return {"error": "Only PDF files are supported."}

    with open(path, "rb") as f:
        reader = pypdf.PdfReader(io.BytesIO(f.read()))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()

    if not text:
        return {"error": "Could not extract text from PDF. Is it a scanned image?"}

    filename = os.path.basename(path)
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resumes (user_id, filename, content)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET filename   = EXCLUDED.filename,
                        content    = EXCLUDED.content,
                        updated_at = NOW()
                """,
                (user_id, filename, text),
            )
        conn.commit()
    finally:
        conn.close()

    return {"message": f"Resume '{filename}' uploaded successfully."}


@tool
def get_user_resume() -> dict:
    """Fetch the current user's resume text from the database.
    Use for gap analysis or to show the user their resume on file.
    Does not modify anything.
    """
    user_id = _context.get("user_id")
    if not user_id:
        return {"error": "No user session active."}

    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT filename, content, updated_at FROM resumes WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return {"error": "No resume on file. Please upload a PDF resume first."}

    return {
        "filename": row["filename"],
        "content": row["content"],
        "updated_at": str(row["updated_at"]),
    }


@tool
def tailor_resume_to_job(job_id: str) -> dict:
    """Tailor the current user's resume for a specific job posting.
    Rewords existing content to match the job's language and priorities.
    NEVER adds skills or experience not already in the resume.
    Saves the result as a PDF and returns the file path.
    - job_id: the job's database ID
    """
    user_id = _context.get("user_id")
    if not user_id:
        return {"error": "No user session active. Cannot access resume."}

    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT content FROM resumes WHERE user_id = %s", (user_id,))
            resume_row = cur.fetchone()
            if not resume_row:
                return {"error": "No resume on file. Please upload a PDF resume first."}

            cur.execute(
                "SELECT title, company, description, skills_must, skills_nice FROM jobs WHERE id = %s",
                (job_id,),
            )
            job_row = cur.fetchone()
            if not job_row:
                return {"error": f"Job '{job_id}' not found in the database."}
    finally:
        conn.close()

    resume_text = resume_row["content"]
    job_title   = job_row["title"] or ""
    job_company = job_row["company"] or ""
    job_desc    = job_row["description"] or ""
    skills_must = ", ".join(job_row["skills_must"] or [])
    skills_nice = ", ".join(job_row["skills_nice"] or [])

    prompt = textwrap.dedent(f"""
        You are a professional resume editor. Lightly tailor the candidate's resume
        for the job posting below.

        STRICT RULES:
        1. Do NOT add any new skills, tools, technologies, experiences, projects,
           certifications, or credentials not already in the resume.
        2. Only rephrase, reorder, or reword existing content to better reflect the
           language and priorities of the job description.
        3. Keep every section present in the original. Do not remove sections.
        4. Preserve all dates, company names, job titles, and education details exactly.
        5. Output only the final tailored resume text — no commentary, no preamble.

        ── JOB POSTING ──────────────────────────────────────────────────────
        Title:    {job_title}
        Company:  {job_company}
        Required skills: {skills_must}
        Nice-to-have:    {skills_nice}

        Description:
        {job_desc}

        ── ORIGINAL RESUME ──────────────────────────────────────────────────
        {resume_text}
    """).strip()

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    try:
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL"),
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        return {"error": f"Resume tailoring failed: {e}. Please try again."}
    tailored_text = message.content[0].text.strip()

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "db", "tailored_resumes",
    )
    os.makedirs(output_dir, exist_ok=True)

    safe_job  = re.sub(r"[^a-zA-Z0-9_-]", "_", job_id)[:40]
    filename  = f"resume_user{user_id}_{safe_job}.pdf"
    filepath  = os.path.join(output_dir, filename)

    _save_pdf(tailored_text, filepath)

    return {
        "message":   "Tailored resume saved successfully.",
        "file":      filepath,
        "job_title": job_title,
        "company":   job_company,
    }


RESUME_TOOLS = [upload_resume, get_user_resume, tailor_resume_to_job]
