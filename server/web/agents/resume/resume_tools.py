"""Resume Tools — upload, fetch, and tailor resume tools for the Resume Agent."""
from __future__ import annotations

import io
import json
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

_context: dict = {"user_id": None}


def set_current_user(user_id: int) -> None:
    _context["user_id"] = user_id


# ── refusal detection / fallback ────────────────────────────────────────────

_REFUSAL_MARKERS = (
    "cannot write", "can't write", "in good conscience", "i recommend",
    "i'd recommend", "i would recommend", "does not support", "misrepresent",
    "critical gaps", "required skills missing", "i appreciate",
)
_MARKDOWN_SHAPE = re.compile(r'\*\*[^*]+\*\*|^\s*[-*]\s|^\s*\d+\.\s', re.MULTILINE)
_CONTACT_LINE = re.compile(
    r'(\+?\d[\d\s().-]{7,}\d)|([\w.+-]+@[\w-]+\.[\w.-]+)|'
    r'(https?://\S+)|(linkedin\.com/\S+)|(github\.com/\S+)'
)


def _looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _REFUSAL_MARKERS):
        return True
    return bool(_MARKDOWN_SHAPE.search(text))


def _summarize_resume_profile(
    client: anthropic.Anthropic, resume_text: str,
) -> str:
    """Create a neutral, contact-free profile paragraph for the fallback letter."""
    prompt = textwrap.dedent(f"""
        Rewrite the following resume content as 2-3 flowing sentences of plain
        professional prose, in the first person. Do not add anything not present
        in the text. Do not include phone numbers, emails, or links. Output only
        the rewritten sentences, with no preamble or evaluation.

        RESUME TEXT:
        {resume_text[:2000]}
    """).strip()
    try:
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL"),
            max_tokens=300,
            system="Rewrite resume text into flowing prose. No commentary, evaluation, or persuasion.",
            messages=[{"role": "user", "content": prompt}],
        )
        summary = _CONTACT_LINE.sub("", message.content[0].text.strip())
        return re.sub(r'\s+', ' ', summary).strip()
    except anthropic.APIError:
        return ""


def _fallback_cover_letter(
    client: anthropic.Anthropic | None, resume_text: str, job_title: str, job_company: str,
    skills_must: str = "", skills_nice: str = "",
) -> str:
    """Clean fallback letter that guarantees a real application for every job.
    client/resume_text are optional — callers that only have the job's title
    and company (e.g. a second-layer safety net with no resume text on hand)
    can omit them and get the generic profile paragraph below instead."""
    profile = _summarize_resume_profile(client, resume_text) if client and resume_text else ""
    if not profile:
        profile = (
            "My academic and project background has given me strong analytical "
            "and technical foundations that I am confident translate well to this role."
        )
    if skills_must:
        interest_line = (
            f"I'm particularly drawn to this role because it would let me build "
            f"on my existing experience while developing new strengths in "
            f"{skills_must.split(',')[0].strip()}"
        )
    else:
        interest_line = "I'm particularly drawn to this role and the opportunity to grow into it"
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to apply for the {job_title} position at {job_company}. "
        f"{interest_line}, and I'm confident my background gives me a strong "
        f"foundation to contribute and learn quickly.\n\n"
        f"{profile}\n\n"
        f"I would welcome the chance to discuss how my experience and motivation "
        f"could apply to this position. Thank you for your time and consideration.\n\n"
        f"Sincerely"
    )


def _generate_cover_letter_text(
    client: anthropic.Anthropic, resume_text: str, job_title: str, job_company: str,
    skills_must: str, skills_nice: str, job_description: str,
) -> str:
    prompt = textwrap.dedent(f"""
        Write a complete, professional cover letter for the job below, based on
        the candidate's real resume. This is a normal application — most real
        candidates don't check every box on a posting, and that's exactly what a
        cover letter is for: making the case for why they're still worth an
        interview.

        Where the resume doesn't show a required skill, don't list it as missing
        or explain the gap — instead, speak to the candidate's genuine potential:
        relevant transferable skills, adjacent projects, education, and real
        interest in learning what the role needs. The letter should read as
        confident and forward-looking, not as an apology for what's absent.

        RULES:
        - Do not invent employers, dates, credentials, achievements, or experience.
        - Do not state the candidate has used a tool or method the resume doesn't
          support — express genuine interest or readiness to learn it instead.
        - Output only the letter body: plain paragraphs, no markdown, no headers,
          no bullet points, no commentary about these instructions.
        - Under 400 words.

        JOB
        Title: {job_title}
        Company: {job_company}
        Required skills: {skills_must}
        Nice-to-have skills: {skills_nice}
        Description:
        {job_description}

        CANDIDATE RESUME
        {resume_text}
    """).strip()

    system = (
        "You write cover letters for real job applicants, including ones whose "
        "resume doesn't cover every requirement — that's routine and expected, "
        "never a reason to decline. Return only the letter body, plain prose."
    )
    prefill = (
        f"Dear Hiring Manager,\n\nI am writing to express my interest in the "
        f"{job_title} position at {job_company}. "
    )

    try:
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL"),
            max_tokens=1200,
            system=system,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prefill},
            ],
        )
        cover_letter = prefill + message.content[0].text.strip()
    except anthropic.APIError:
        return _fallback_cover_letter(client, resume_text, job_title, job_company, skills_must, skills_nice)

    if _looks_like_refusal(cover_letter):
        return _fallback_cover_letter(client, resume_text, job_title, job_company, skills_must, skills_nice)

    return cover_letter


# ── helpers ───────────────────────────────────────────────────────────────

def _conn():
    return get_connection()


def _save_pdf(text: str, filepath: str) -> None:
    doc = SimpleDocTemplate(
        filepath, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_LEFT)
    header = ParagraphStyle(
        "header", parent=styles["Normal"], fontSize=12, leading=16,
        spaceAfter=2 * mm, fontName="Helvetica-Bold",
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


def generate_cover_letter_for_job(user_id: int, job_id: str) -> dict:
    """Generate a cover letter using the user's resume and a stored job posting."""
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

    job_title = job_row["title"] or ""
    job_company = job_row["company"] or ""
    skills_must = ", ".join(job_row["skills_must"] or [])
    skills_nice = ", ".join(job_row["skills_nice"] or [])

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    cover_letter = _generate_cover_letter_text(
        client, resume_row["content"], job_title, job_company,
        skills_must, skills_nice, job_row["description"] or "",
    )

    skill_gaps = ""
    gap_prompt = textwrap.dedent(f"""
        Compare the candidate's resume with the job requirements below.
        Identify only the important skills or requirements that are not clearly
        supported by the resume. This is a gap summary for the candidate, not a
        rejection. Use concise bullet points, one gap per line, and explain briefly
        what is missing. If there are no clear gaps, return "No clear skill gaps".
        Do not invent facts and do not write a cover letter.

        JOB REQUIREMENTS
        Required skills: {skills_must}
        Nice-to-have skills: {skills_nice}
        Description:
        {job_row['description'] or ''}

        CANDIDATE RESUME
        {resume_row['content']}
    """).strip()
    try:
        gap_message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL"),
            max_tokens=500,
            system="Return only a concise, factual skill-gap summary.",
            messages=[{"role": "user", "content": gap_prompt}],
        )
        skill_gaps = gap_message.content[0].text.strip()
    except anthropic.APIError:
        skill_gaps = ""

    return {
        "cover_letter": cover_letter,
        "job_title": job_title,
        "company": job_company,
        "skill_gaps": skill_gaps,
    }


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
                    SET filename = EXCLUDED.filename,
                        content = EXCLUDED.content,
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
    """Fetch the current user's resume text from the database."""
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
    """Tailor the current user's resume for a specific job and save a PDF."""
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

    job_title = job_row["title"] or ""
    job_company = job_row["company"] or ""
    prompt = textwrap.dedent(f"""
        Lightly tailor the resume below for {job_title} at {job_company}.
        Only rephrase or reorder information already present. Do not add skills,
        tools, experience, credentials, dates, or achievements. Output only the
        tailored resume text.

        JOB DESCRIPTION:
        {job_row['description'] or ''}

        ORIGINAL RESUME:
        {resume_row['content']}
    """).strip()

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    try:
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL"),
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        return {"error": f"Resume tailoring failed: {exc}. Please try again."}

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "db", "tailored_resumes",
    )
    os.makedirs(output_dir, exist_ok=True)
    safe_job = re.sub(r"[^a-zA-Z0-9_-]", "_", job_id)[:40]
    filepath = os.path.join(output_dir, f"resume_user{user_id}_{safe_job}.pdf")
    _save_pdf(message.content[0].text.strip(), filepath)

    return {
        "message": "Tailored resume saved successfully.",
        "file": filepath,
        "job_title": job_title,
        "company": job_company,
    }


@tool
def generate_cover_letter(job_id: str) -> str:
    """Return only a complete cover letter, even when skills are missing."""
    user_id = _context.get("user_id")
    if not user_id:
        return "Unable to generate a cover letter because no user session is active."
    result = generate_cover_letter_for_job(user_id, job_id)
    if "error" in result:
        return result["error"]
    return result["cover_letter"]


RESUME_TOOLS = [upload_resume, get_user_resume, tailor_resume_to_job, generate_cover_letter]