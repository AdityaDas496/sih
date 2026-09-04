from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .detection import Person2InputDetection, CanonicalDetection

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    person1_model_loaded: bool = False
    facilities_loaded: int = 0
    cached_detections_count: int = 0


class StatisticsResponse(BaseModel):
    total_detected_events: int
    industrial_count: int
    forest_count: int
    other_natural_count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    by_facility_type: Dict[str, int] = Field(default_factory=dict)
    by_branch: Dict[str, int] = Field(default_factory=dict)


class ClassifyRequest(BaseModel):
    detection: Person2InputDetection


class ProcessBatchRequest(BaseModel):
    detections: List[Person2InputDetection]


class ProcessBatchResponse(BaseModel):
    total_processed: int
    successful: int
    failed: int
    events: List[CanonicalDetection]
    errors: List[Dict[str, Any]] = Field(default_factory=list)
