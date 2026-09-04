from typing import List, Dict, Any
from app.schemas.detection import CanonicalDetection

class GeoJSONService:
    @staticmethod
    def to_feature_collection(detections: List[CanonicalDetection]) -> Dict[str, Any]:
        """Convert a list of CanonicalDetection objects into a map-ready GeoJSON FeatureCollection."""
        features = []
        for det in detections:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [det.longitude, det.latitude]
                },
                "properties": {
                    "detection_id": det.detection_id,
                    "fire_type": det.fire_type,
                    "classification_confidence": det.classification_confidence,
                    "severity": det.severity,
                    "branch": det.branch,
                    "frp": det.frp,
                    "brightness": det.brightness,
                    "bright_t31": det.bright_t31,
                    "confidence": det.confidence,
                    "satellite": det.satellite,
                    "instrument": det.instrument,
                    "acq_date": det.acq_date,
                    "acq_time": det.acq_time,
                    "distance_to_nearest_industry_km": det.distance_to_nearest_industry_km,
                    "nearest_facility_id": det.nearest_facility_id,
                    "nearest_facility_type": det.nearest_facility_type,
                    "nearest_facility_name": det.nearest_facility_name,
                    "worldcover_class": det.worldcover_class,
                    "contributing_factors": det.contributing_factors,
                    "anomaly_score": det.anomaly_score
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }


geojson_service = GeoJSONService()
