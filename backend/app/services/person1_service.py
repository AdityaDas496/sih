import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import joblib

from app.config import settings
from app.schemas.detection import Person2InputDetection, CanonicalDetection
from app.services.facility_service import facility_service
from app.services.worldcover_service import worldcover_service
from app.services.person2_service import person2_service

CLASS_MAPPING = {
    "industrial_proxy": "INDUSTRIAL",
    "forest_proxy": "FOREST",
    "other_natural_proxy": "OTHER_NATURAL",
    # Direct fallbacks if model predicts canonical names
    "INDUSTRIAL": "INDUSTRIAL",
    "FOREST": "FOREST",
    "OTHER_NATURAL": "OTHER_NATURAL"
}


class Person1Service:
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or settings.PERSON1_MODEL_PATH
        self.model = None
        self.feature_columns: List[str] = []
        self.numeric_medians: Dict[str, float] = {}
        self.classes: List[str] = []
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        """Load Person 1 trained Random Forest model artifact."""
        if not self.model_path.exists():
            print(f"[Person1Service] Error: Model artifact not found at {self.model_path}")
            return

        try:
            artifact = joblib.load(self.model_path)
            self.model = artifact.get("model")
            self.feature_columns = artifact.get("feature_columns", [])
            self.numeric_medians = artifact.get("numeric_medians", {})
            self.classes = artifact.get("classes", [])
            self.is_loaded = True
            print(f"[Person1Service] Model loaded successfully. Feature columns count: {len(self.feature_columns)}")
        except Exception as e:
            print(f"[Person1Service] Failed to load model artifact: {e}")

    @staticmethod
    def derive_temporal_features(acq_date: str, acq_time: str) -> Dict[str, float]:
        """Derive temporal features matching Person 1 training preprocessing."""
        time_str = str(acq_time).zfill(4)
        dt_str = f"{acq_date} {time_str}"
        dt = pd.to_datetime(dt_str, format="%Y-%m-%d %H%M", errors="coerce")

        if pd.isna(dt):
            hour = 12.0
            month = 6
            dayofyear = 180
        else:
            hour = dt.hour + dt.minute / 60.0
            month = dt.month
            dayofyear = dt.dayofyear

        sin_hour = float(np.sin(2 * np.pi * hour / 24.0))
        cos_hour = float(np.cos(2 * np.pi * hour / 24.0))
        sin_month = float(np.sin(2 * np.pi * month / 12.0))
        cos_month = float(np.cos(2 * np.pi * month / 12.0))
        is_day = 1 if (6.0 <= hour < 18.0) else 0

        return {
            "hour": hour,
            "month": float(month),
            "dayofyear": float(dayofyear),
            "sin_hour": sin_hour,
            "cos_hour": cos_hour,
            "sin_month": sin_month,
            "cos_month": cos_month,
            "is_day": float(is_day)
        }

    def enrich_detection(self, detection: Person2InputDetection) -> Dict[str, Any]:
        """Enrich a Person 2 detection record with facility, WorldCover, and temporal features."""
        # 1. Facility lookup
        dist_km, fac_id, fac_type, fac_name, fac_props = facility_service.get_nearest_facility(
            detection.latitude, detection.longitude
        )

        # 2. WorldCover lookup
        wc_features = worldcover_service.sample_landcover(detection.latitude, detection.longitude)

        # 3. Temporal features
        time_features = self.derive_temporal_features(detection.acq_date, detection.acq_time)

        # Combine all features into flat dictionary
        enriched = {
            "latitude": detection.latitude,
            "longitude": detection.longitude,
            "acq_date": detection.acq_date,
            "acq_time": str(detection.acq_time).zfill(4),
            "frp": detection.frp,
            "brightness": detection.brightness,
            "bright_t31": detection.bright_t31,
            "scan": detection.scan,
            "track": detection.track,
            "confidence": detection.confidence,
            "satellite": detection.satellite,
            "instrument": detection.instrument,
            "daynight": detection.daynight,
            "type": detection.type,
            "fire_event_detected": detection.fire_event_detected,
            "branch": detection.branch or "industrial",
            "anomaly_score": detection.anomaly_score if detection.anomaly_score is not None else 0.5,
            
            # Enriched fields
            "distance_to_nearest_industry_km": dist_km,
            "nearest_facility_id": fac_id,
            "nearest_facility_type": fac_type,
            "nearest_facility_name": fac_name,
            **wc_features,
            **time_features
        }

        return enriched

    def classify_single(self, detection: Person2InputDetection, idx: int = 1) -> CanonicalDetection:
        """Classify a single Person 2 detection record."""
        enriched = self.enrich_detection(detection)
        
        det_id = detection.detection_id or f"DET_{idx:05d}"
        
        # Prepare feature vector for model input
        feature_row = {}
        for col in self.feature_columns:
            if col in enriched:
                feature_row[col] = enriched[col]
            elif col.startswith("nearest_facility_type_"):
                # One-hot encoded facility type column
                category = col.replace("nearest_facility_type_", "")
                facility_type_val = enriched.get("nearest_facility_type", "unknown")
                feature_row[col] = 1.0 if str(facility_type_val).lower() == category.lower() else 0.0
            else:
                # Impute missing feature using median from training artifact
                feature_row[col] = self.numeric_medians.get(col, 0.0)

        df_X = pd.DataFrame([feature_row])[self.feature_columns]

        # Model Inference
        if self.is_loaded and self.model is not None:
            raw_pred = self.model.predict(df_X)[0]
            probs = self.model.predict_proba(df_X)[0]
            conf = float(np.max(probs))
        else:
            # Fallback heuristic if model not loaded
            dist = enriched["distance_to_nearest_industry_km"]
            if dist <= 1.0 or enriched.get("builtup_landcover") == 1:
                raw_pred = "industrial_proxy"
                conf = 0.92
            elif enriched.get("forest_like_landcover") == 1 and dist >= 5.0:
                raw_pred = "forest_proxy"
                conf = 0.88
            else:
                raw_pred = "other_natural_proxy"
                conf = 0.85

        fire_type = CLASS_MAPPING.get(raw_pred, "OTHER_NATURAL")
        severity = person2_service.calculate_severity(detection.frp, detection.brightness, detection.anomaly_score)

        # Construct contributing factors description
        factors = (
            f"Nearest facility: {enriched['nearest_facility_name']} ({enriched['nearest_facility_type']}, "
            f"{enriched['distance_to_nearest_industry_km']} km); "
            f"WorldCover class: {enriched['worldcover_class']}; "
            f"FRP: {detection.frp} MW, Brightness: {detection.brightness} K"
        )

        return CanonicalDetection(
            detection_id=det_id,
            latitude=detection.latitude,
            longitude=detection.longitude,
            acq_date=detection.acq_date,
            acq_time=enriched["acq_time"],
            fire_type=fire_type,
            classification_confidence=round(conf, 4),
            severity=severity,
            branch=enriched["branch"],
            frp=detection.frp,
            brightness=detection.brightness,
            bright_t31=detection.bright_t31,
            confidence=detection.confidence,
            satellite=detection.satellite,
            instrument=detection.instrument,
            distance_to_nearest_industry_km=enriched["distance_to_nearest_industry_km"],
            nearest_facility_id=enriched["nearest_facility_id"],
            nearest_facility_type=enriched["nearest_facility_type"],
            nearest_facility_name=enriched["nearest_facility_name"],
            worldcover_class=enriched["worldcover_class"],
            contributing_factors=factors,
            anomaly_score=enriched["anomaly_score"],
            fire_event_detected=detection.fire_event_detected
        )


# Global singleton instance
person1_service = Person1Service()
