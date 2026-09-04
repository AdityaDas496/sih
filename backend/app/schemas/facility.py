from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

class FacilityProperties(BaseModel):
    facility_id: str
    facility_type: str
    facility_name: str
    country: str = "India"
    status: Optional[str] = None
    capacity: Optional[Any] = None
    coordinate_accuracy: Optional[str] = None


class GeoJSONGeometryPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=3, description="[longitude, latitude]")


class FacilityFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometryPoint
    properties: FacilityProperties


class FacilityCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[FacilityFeature]


class FacilityResponse(BaseModel):
    facility_id: str
    facility_type: str
    facility_name: str
    latitude: float
    longitude: float
    country: str
    status: Optional[str] = None
    capacity: Optional[Any] = None
    coordinate_accuracy: Optional[str] = None
