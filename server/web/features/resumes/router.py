from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from core.security import get_current_user
from features.resumes import service
from features.resumes.schemas import ResumeListItem, ResumeDetail, ResumeUpdateRequest

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    return await service.upload_resume(int(user_id), file)


@router.get("", response_model=List[ResumeListItem])
def list_resumes(user_id: str = Depends(get_current_user)):
    return service.list_my_resumes(int(user_id))


@router.get("/me")
def get_my_resume(user_id: str = Depends(get_current_user)):
    return service.get_my_resume(int(user_id))


@router.delete("/me", status_code=204)
def delete_my_resume(user_id: str = Depends(get_current_user)):
    service.delete_my_resume(int(user_id))


@router.get("/{resume_id}", response_model=ResumeDetail)
def get_resume_detail(resume_id: int, user_id: str = Depends(get_current_user)):
    return service.get_resume_detail(int(user_id), resume_id)


@router.patch("/{resume_id}", response_model=ResumeDetail)
def update_resume(resume_id: int, data: ResumeUpdateRequest, user_id: str = Depends(get_current_user)):
    return service.update_resume(int(user_id), resume_id, data.title, data.is_active)


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, user_id: str = Depends(get_current_user)):
    service.delete_my_resume(int(user_id), resume_id)
