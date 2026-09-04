from typing import Dict, Any, Tuple, Optional
from app.schemas.detection import Person2InputDetection

class Person2Service:
    @staticmethod
    def validate_and_filter(detection: Person2InputDetection) -> Tuple[bool, Optional[str]]:
        """Validate Person 2 detection record and check fire_event_detected flag."""
        if not detection.fire_event_detected:
            return False, "Skipping record: fire_event_detected is False"

        if not (-90.0 <= detection.latitude <= 90.0 and -180.0 <= detection.longitude <= 180.0):
            return False, f"Invalid latitude/longitude coordinates: ({detection.latitude}, {detection.longitude})"

        if not detection.acq_date or not detection.acq_time:
            return False, "Missing acquisition date or time"

        return True, None

    @staticmethod
    def calculate_severity(frp: float, brightness: float, anomaly_score: Optional[float] = None) -> str:
        """Calculate fire event severity level (HIGH, MEDIUM, LOW)."""
        score = anomaly_score if anomaly_score is not None else 0.5

        if frp >= 15.0 or brightness >= 340.0 or score >= 0.85:
            return "HIGH"
        elif frp >= 5.0 or brightness >= 320.0 or score >= 0.60:
            return "MEDIUM"
        else:
            return "LOW"


person2_service = Person2Service()
