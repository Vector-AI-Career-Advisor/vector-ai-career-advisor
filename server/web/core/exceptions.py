"""Custom exception classes and FastAPI exception handlers."""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


async def app_error_handler(request: Request, exc: AppError):
    log.warning(
        "%s %s → %d | %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
