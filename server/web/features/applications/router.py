from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.security import get_current_user
from features.applications import service

router = APIRouter()


class ApplicationCreate(BaseModel):
    job_id: str


class ApplicationUpdate(BaseModel):
    status: str


@router.get("/")
def list_my_applications(
    status: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    return service.list_applications(int(user_id), status)


@router.post("/", status_code=201)
def apply_to_job(
    body: ApplicationCreate,
    user_id: str = Depends(get_current_user),
):
    try:
        return service.create_application(int(user_id), body.job_id)
    except ValueError as e:
        if str(e) == "already_applied":
            raise HTTPException(status_code=409, detail="Already applied to this job.")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{job_id}")
def update_application_status(
    job_id: str,
    body: ApplicationUpdate,
    user_id: str = Depends(get_current_user),
):
    try:
        return service.update_status(int(user_id), job_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
