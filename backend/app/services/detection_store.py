from typing import List, Dict, Optional, Any
import pandas as pd
from app.config import settings
from app.schemas.detection import CanonicalDetection, Person2InputDetection
from app.services.person1_service import person1_service, CLASS_MAPPING
from app.services.person2_service import person2_service

class DetectionStore:
    def __init__(self):
        self._detections: List[CanonicalDetection] = []
        self._by_id: Dict[str, CanonicalDetection] = {}

    def load_initial_dataset(self):
        """Load and classify sample dataset on startup."""
        sample_path = settings.SAMPLE_PREDICTIONS_PATH
        if not sample_path.exists():
            print(f"[DetectionStore] Sample dataset not found at {sample_path}")
            return

        try:
            print(f"[DetectionStore] Ingesting and classifying sample events from {sample_path}...")
            df = pd.read_csv(sample_path)
            
            count = 0
            has_precomputed = "predicted_fire_type_v0" in df.columns
            
            for idx, row in df.iterrows():
                if has_precomputed:
                    raw_type = str(row.get("predicted_fire_type_v0", "other_natural_proxy"))
                    fire_type = CLASS_MAPPING.get(raw_type, "OTHER_NATURAL")
                    
                    frp = float(row.get("frp", 1.0))
                    brightness = float(row.get("brightness", 300.0))
                    anomaly = float(row.get("classification_confidence_v0", 0.85))
                    severity = person2_service.calculate_severity(frp, brightness, anomaly)
                    
                    canonical = CanonicalDetection(
                        detection_id=f"DET_{idx+1:05d}",
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        acq_date=str(row["acq_date"]),
                        acq_time=str(row["acq_time"]).zfill(4),
                        fire_type=fire_type,
                        classification_confidence=round(float(row.get("classification_confidence_v0", 0.9)), 4),
                        severity=severity,
                        branch=str(row.get("weak_label", row.get("proposed_weak_class", "industrial"))).replace("_proxy", ""),
                        frp=frp,
                        brightness=brightness,
                        bright_t31=float(row.get("bright_t31", 290.0)),
                        confidence=str(row.get("confidence", "n")),
                        satellite=str(row.get("satellite", "SNPP")),
                        instrument=str(row.get("instrument", "VIIRS")),
                        distance_to_nearest_industry_km=float(row.get("distance_to_nearest_industry_km", 0.0)),
                        nearest_facility_id=str(row.get("nearest_facility_id")) if pd.notna(row.get("nearest_facility_id")) else None,
                        nearest_facility_type=str(row.get("nearest_facility_type")) if pd.notna(row.get("nearest_facility_type")) else None,
                        nearest_facility_name=str(row.get("nearest_facility_name")) if pd.notna(row.get("nearest_facility_name")) else None,
                        worldcover_class=int(row["worldcover_class"]) if pd.notna(row.get("worldcover_class")) else 40,
                        contributing_factors=f"Nearest facility: {row.get('nearest_facility_name')}; FRP: {frp} MW",
                        anomaly_score=anomaly,
                        fire_event_detected=True
                    )
                else:
                    p2_input = Person2InputDetection(
                        detection_id=f"DET_{idx+1:05d}",
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        acq_date=str(row["acq_date"]),
                        acq_time=str(row["acq_time"]),
                        brightness=float(row["brightness"]),
                        bright_t31=float(row["bright_t31"]),
                        frp=float(row["frp"]),
                        scan=float(row.get("scan", 0.4)),
                        track=float(row.get("track", 0.4)),
                        confidence=str(row.get("confidence", "n")),
                        satellite=str(row.get("satellite", "SNPP")),
                        instrument=str(row.get("instrument", "VIIRS")),
                        daynight="N" if float(row.get("is_day", 0)) == 0 else "D",
                        type=int(row.get("type", 0)),
                        fire_event_detected=True,
                        branch=str(row.get("weak_label", "industrial")),
                        anomaly_score=float(row.get("classification_confidence_v0", 0.85))
                    )
                    canonical = person1_service.classify_single(p2_input, idx=idx+1)

                self._detections.append(canonical)
                self._by_id[canonical.detection_id] = canonical
                count += 1

            print(f"[DetectionStore] Successfully loaded and classified {count} events.")

        except Exception as e:
            print(f"[DetectionStore] Failed to load sample dataset: {e}")

    def get_all(self) -> List[CanonicalDetection]:
        return self._detections

    def get_by_id(self, detection_id: str) -> Optional[CanonicalDetection]:
        return self._by_id.get(detection_id)

    def add(self, canonical: CanonicalDetection):
        self._detections.append(canonical)
        self._by_id[canonical.detection_id] = canonical

    def filter(
        self,
        fire_type: Optional[str] = None,
        severity: Optional[str] = None,
        branch: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_confidence: Optional[float] = None,
        facility_type: Optional[str] = None,
        limit: int = 500,
        offset: int = 0
    ) -> List[CanonicalDetection]:
        results = []
        for det in self._detections:
            if fire_type and det.fire_type.upper() != fire_type.upper():
                continue
            if severity and det.severity.upper() != severity.upper():
                continue
            if branch and det.branch.lower() != branch.lower():
                continue
            if date_from and det.acq_date < date_from:
                continue
            if date_to and det.acq_date > date_to:
                continue
            if min_confidence is not None and det.classification_confidence < min_confidence:
                continue
            if facility_type and det.nearest_facility_type:
                if det.nearest_facility_type.lower() != facility_type.lower():
                    continue

            results.append(det)

        return results[offset:offset+limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Compute summary statistics over all classified events."""
        stats = {
            "total_detected_events": len(self._detections),
            "industrial_count": 0,
            "forest_count": 0,
            "other_natural_count": 0,
            "high_severity_count": 0,
            "medium_severity_count": 0,
            "low_severity_count": 0,
            "by_facility_type": {},
            "by_branch": {}
        }

        for det in self._detections:
            if det.fire_type == "INDUSTRIAL":
                stats["industrial_count"] += 1
            elif det.fire_type == "FOREST":
                stats["forest_count"] += 1
            elif det.fire_type == "OTHER_NATURAL":
                stats["other_natural_count"] += 1

            if det.severity == "HIGH":
                stats["high_severity_count"] += 1
            elif det.severity == "MEDIUM":
                stats["medium_severity_count"] += 1
            elif det.severity == "LOW":
                stats["low_severity_count"] += 1

            if det.nearest_facility_type:
                ft = det.nearest_facility_type
                stats["by_facility_type"][ft] = stats["by_facility_type"].get(ft, 0) + 1

            if det.branch:
                b = det.branch
                stats["by_branch"][b] = stats["by_branch"].get(b, 0) + 1

        return stats


detection_store = DetectionStore()
