from fastapi import APIRouter
from app.schemas.response import HealthResponse
from app.services.person1_service import person1_service
from app.services.facility_service import facility_service

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health():
    """Simple health check endpoint."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        person1_model_loaded=person1_service.is_loaded,
        facilities_loaded=len(facility_service.facilities)
    )
