import io
import logging
import zipfile
from xml.etree import ElementTree as ET

from fastapi import HTTPException, UploadFile
import pypdf
from features.resumes import repository

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
    log.info("Resume uploaded for user %s: %s", user_id, file.filename)
    return {"message": "Resume uploaded successfully", "filename": file.filename}


def get_my_resume(user_id: int) -> dict:
    resume = repository.get_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume on file")
    return resume


def delete_my_resume(user_id: int) -> None:
    repository.delete_resume(user_id)
