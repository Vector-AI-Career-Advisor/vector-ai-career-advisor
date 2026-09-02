from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user
from features.saved_filters import service
from features.saved_filters.schemas import SavedFilterCreate, SavedFilterOut

router = APIRouter()


@router.get("/", response_model=List[SavedFilterOut])
def list_saved_filters(user_id: str = Depends(get_current_user)):
    return service.list_saved_filters(int(user_id))


@router.post("/", response_model=SavedFilterOut, status_code=201)
def create_saved_filter(body: SavedFilterCreate, user_id: str = Depends(get_current_user)):
    return service.create_saved_filter(int(user_id), body)


@router.delete("/{filter_id}")
def delete_saved_filter(filter_id: int, user_id: str = Depends(get_current_user)):
    if not service.delete_saved_filter(int(user_id), filter_id):
        raise HTTPException(status_code=404, detail="Saved filter not found.")
    return {"success": True}
