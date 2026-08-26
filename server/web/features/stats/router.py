from fastapi import APIRouter, Depends
from core.security import get_current_user
from features.stats import service

router = APIRouter()


@router.get("/stats")
def get_stats(user_id: str = Depends(get_current_user)):
    return service.get_stats()
