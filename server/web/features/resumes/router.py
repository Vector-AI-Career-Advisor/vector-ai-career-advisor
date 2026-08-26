from __future__ import annotations
from fastapi import APIRouter, Depends, UploadFile, File
from core.security import get_current_user
from features.resumes import service

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    return await service.upload_resume(int(user_id), file)


@router.get("/me")
def get_my_resume(user_id: str = Depends(get_current_user)):
    return service.get_my_resume(int(user_id))


@router.delete("/me", status_code=204)
def delete_my_resume(user_id: str = Depends(get_current_user)):
    service.delete_my_resume(int(user_id))
