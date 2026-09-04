from fastapi import APIRouter
from app.schemas.response import StatisticsResponse
from app.services.detection_store import detection_store

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])

@router.get("", response_model=StatisticsResponse)
def get_statistics():
    """Return summary statistics of classified fire events."""
    stats = detection_store.get_statistics()
    return StatisticsResponse(**stats)
