from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.schemas.facility import FacilityResponse, FacilityCollection
from app.services.facility_service import facility_service

router = APIRouter(prefix="/api/facilities", tags=["Facilities"])

@router.get("", response_model=List[FacilityResponse])
def get_facilities(facility_type: Optional[str] = Query(None, description="Filter by facility type (e.g., steel, cement, coal_power)")):
    """Return industrial facilities for visualization and analysis."""
    return facility_service.list_facilities(facility_type=facility_type)


@router.get("/geojson", response_model=FacilityCollection)
def get_facilities_geojson(facility_type: Optional[str] = Query(None, description="Filter by facility type")):
    """Return map-ready GeoJSON FeatureCollection of industrial facilities."""
    return facility_service.get_facilities_geojson(facility_type=facility_type)


@router.get("/{facility_id}", response_model=FacilityResponse)
def get_facility_by_id(facility_id: str):
    """Return detail view for a specific industrial facility by ID."""
    fac = facility_service.get_facility_by_id(facility_id)
    if not fac:
        raise HTTPException(status_code=404, detail=f"Facility with ID '{facility_id}' not found.")
    return fac
