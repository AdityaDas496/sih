from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

class Person2InputDetection(BaseModel):
    """Raw/Confirmed detection record provided by Person 2."""
    model_config = ConfigDict(extra="ignore")

    detection_id: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    acq_date: str = Field(..., description="Acquisition date (YYYY-MM-DD)")
    acq_time: str = Field(..., description="Acquisition time (HHMM)")
    brightness: float = Field(..., description="Channel 21/22 brightness temperature (K)")
    bright_t31: float = Field(..., description="Channel 31 brightness temperature (K)")
    frp: float = Field(..., description="Fire Radiative Power (MW)")
    scan: float = Field(0.4, description="Scan pixel size")
    track: float = Field(0.4, description="Track pixel size")
    confidence: str = Field("n", description="Detection confidence level (e.g., n, h, l)")
    satellite: str = Field("SNPP", description="Satellite name")
    instrument: str = Field("VIIRS", description="Instrument name")
    daynight: str = Field("N", description="Day or Night flag (D/N)")
    type: int = Field(0, description="VIIRS spot type (0=presumed vegetation, 2=other static land source)")
    
    # Person 2 specific detector fields
    fire_event_detected: bool = Field(True, description="Person 2 detector flag: is this an abnormal fire?")
    branch: Optional[str] = Field("industrial", description="Person 2 detector branch (e.g. industrial, forest, general)")
    anomaly_score: Optional[float] = Field(0.5, description="Person 2 thermal anomaly score (0.0 to 1.0)")


class CanonicalDetection(BaseModel):
    """Unified canonical classified fire event returned by the backend."""
    detection_id: str
    latitude: float
    longitude: float
    acq_date: str
    acq_time: str
    fire_type: Literal["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]
    classification_confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction probability")
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    branch: str
    frp: float
    brightness: float
    bright_t31: float
    confidence: str
    satellite: str
    instrument: str
    distance_to_nearest_industry_km: float
    nearest_facility_id: Optional[str] = None
    nearest_facility_type: Optional[str] = None
    nearest_facility_name: Optional[str] = None
    worldcover_class: Optional[int] = None
    contributing_factors: Optional[str] = None
    anomaly_score: Optional[float] = None
    fire_event_detected: bool = True


class DetectionFilterParams(BaseModel):
    """Query filter parameters for detection listing."""
    fire_type: Optional[Literal["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]] = None
    severity: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    branch: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    facility_type: Optional[str] = None
    limit: int = Field(500, ge=1, le=10000)
    offset: int = Field(0, ge=0)
