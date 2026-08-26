import io
import logging

from fastapi import HTTPException, UploadFile
import pypdf
from features.resumes import repository

log = logging.getLogger(__name__)


def _extract_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


async def upload_resume(user_id: int, file: UploadFile) -> dict:
    if not file.filename.lower().endswith(".pdf"):
        log.warning("Resume upload rejected for user %s — not a PDF: %s", user_id, file.filename)
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    text = _extract_text(contents)
    if not text:
        log.warning("Resume upload rejected for user %s — no extractable text: %s", user_id, file.filename)
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    repository.save_resume(user_id, file.filename, text)
    log.info("Resume uploaded for user %s: %s", user_id, file.filename)
    return {"message": "Resume uploaded successfully", "filename": file.filename}


def get_my_resume(user_id: int) -> dict:
    resume = repository.get_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume on file")
    return resume


def delete_my_resume(user_id: int) -> None:
    repository.delete_resume(user_id)
