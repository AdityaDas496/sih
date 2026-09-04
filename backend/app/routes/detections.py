from typing import Optional, List, Literal, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body, status

from app.schemas.detection import Person2InputDetection, CanonicalDetection
from app.schemas.response import ClassifyRequest, ProcessBatchRequest, ProcessBatchResponse
from app.services.detection_store import detection_store
from app.services.person1_service import person1_service
from app.services.person2_service import person2_service
from app.services.geojson_service import geojson_service

router = APIRouter(prefix="/api/detections", tags=["Detections"])


@router.get("", response_model=List[CanonicalDetection])
def list_detections(
    fire_type: Optional[Literal["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]] = Query(None, description="Filter by classified fire type"),
    severity: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = Query(None, description="Filter by event severity"),
    branch: Optional[str] = Query(None, description="Filter by Person 2 detector branch"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum model classification confidence"),
    facility_type: Optional[str] = Query(None, description="Filter by nearest industrial facility type"),
    limit: int = Query(500, ge=1, le=10000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Return classified fire detection events with optional filtering parameters."""
    return detection_store.filter(
        fire_type=fire_type,
        severity=severity,
        branch=branch,
        date_from=date_from,
        date_to=date_to,
        min_confidence=min_confidence,
        facility_type=facility_type,
        limit=limit,
        offset=offset
    )


@router.get("/geojson", response_model=Dict[str, Any])
def get_detections_geojson(
    fire_type: Optional[Literal["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]] = Query(None, description="Filter by fire type"),
    severity: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = Query(None, description="Filter by severity"),
    branch: Optional[str] = Query(None, description="Filter by Person 2 branch"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum classification confidence"),
    facility_type: Optional[str] = Query(None, description="Filter by facility type"),
    limit: int = Query(2000, ge=1, le=10000, description="Max points for GeoJSON FeatureCollection")
):
    """Return a map-ready GeoJSON FeatureCollection of classified fire events.
    
    Each Feature geometry strictly uses original satellite detection coordinates [longitude, latitude].
    """
    filtered = detection_store.filter(
        fire_type=fire_type,
        severity=severity,
        branch=branch,
        date_from=date_from,
        date_to=date_to,
        min_confidence=min_confidence,
        facility_type=facility_type,
        limit=limit,
        offset=0
    )
    return geojson_service.to_feature_collection(filtered)


@router.get("/{detection_id}", response_model=CanonicalDetection)
def get_detection_by_id(detection_id: str):
    """Return detailed information for a specific classified fire detection event."""
    event = detection_store.get_by_id(detection_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Detection event '{detection_id}' not found.")
    return event


@router.post("/classify", response_model=CanonicalDetection)
def classify_detection(payload: Person2InputDetection = Body(...)):
    """Classify a single Person 2 detection record through the Person 1 pipeline.
    
    This endpoint enriches the detection with facility, WorldCover, and temporal features,
    then executes Person 1's ML classifier.
    """
    is_valid, err_msg = person2_service.validate_and_filter(payload)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    canonical = person1_service.classify_single(payload)
    detection_store.add(canonical)
    return canonical


@router.post("/process", response_model=ProcessBatchResponse)
def process_batch_detections(payload: ProcessBatchRequest = Body(...)):
    """Process a batch of Person 2 confirmed detections through the backend pipeline."""
    successful = []
    errors = []

    for idx, det in enumerate(payload.detections):
        try:
            is_valid, err_msg = person2_service.validate_and_filter(det)
            if not is_valid:
                errors.append({"index": idx, "detection_id": det.detection_id, "error": err_msg})
                continue

            canonical = person1_service.classify_single(det, idx=idx+1)
            detection_store.add(canonical)
            successful.append(canonical)
        except Exception as e:
            errors.append({"index": idx, "detection_id": det.detection_id, "error": str(e)})

    return ProcessBatchResponse(
        total_processed=len(payload.detections),
        successful=len(successful),
        failed=len(errors),
        events=successful,
        errors=errors
    )
