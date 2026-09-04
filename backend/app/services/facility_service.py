import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy.spatial import cKDTree

from app.config import settings
from app.schemas.facility import FacilityResponse, FacilityFeature, FacilityCollection, FacilityProperties, GeoJSONGeometryPoint

EARTH_RADIUS_KM = 6371.0088

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance in kilometers between two points on Earth."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def latlon_to_cartesian(lat: float, lon: float) -> Tuple[float, float, float]:
    """Convert latitude/longitude in degrees to 3D Cartesian coordinates on unit sphere."""
    phi = math.radians(lat)
    lam = math.radians(lon)
    x = math.cos(phi) * math.cos(lam)
    y = math.cos(phi) * math.sin(lam)
    z = math.sin(phi)
    return x, y, z


class FacilityService:
    def __init__(self, geojson_path: Optional[Path] = None):
        self.geojson_path = geojson_path or settings.GIS_FACILITIES_PATH
        self.facilities: List[Dict[str, Any]] = []
        self.facilities_by_id: Dict[str, Dict[str, Any]] = {}
        self.kdtree: Optional[cKDTree] = None
        self.coordinates_3d: Optional[np.ndarray] = None
        self._load_facilities()

    def _load_facilities(self):
        """Load industrial facility GeoJSON and build KDTree spatial index."""
        if not self.geojson_path.exists():
            print(f"[FacilityService] Warning: GeoJSON file not found at {self.geojson_path}")
            return

        try:
            with open(self.geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            features = data.get("features", [])
            coords_3d_list = []

            for feat in features:
                geometry = feat.get("geometry", {})
                props = feat.get("properties", {})
                
                if geometry.get("type") == "Point":
                    coords = geometry.get("coordinates", [])
                    if len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                        fac_id = str(props.get("facility_id", f"FAC_{len(self.facilities)+1}"))
                        
                        fac_item = {
                            "facility_id": fac_id,
                            "facility_type": str(props.get("facility_type", "unknown")),
                            "facility_name": str(props.get("facility_name", "Unknown Facility")),
                            "latitude": lat,
                            "longitude": lon,
                            "country": str(props.get("country", "India")),
                            "status": props.get("status"),
                            "capacity": props.get("capacity"),
                            "coordinate_accuracy": props.get("coordinate_accuracy", "approximate")
                        }
                        
                        self.facilities.append(fac_item)
                        self.facilities_by_id[fac_id] = fac_item
                        
                        cx, cy, cz = latlon_to_cartesian(lat, lon)
                        coords_3d_list.append([cx, cy, cz])

            if coords_3d_list:
                self.coordinates_3d = np.array(coords_3d_list)
                self.kdtree = cKDTree(self.coordinates_3d)

            print(f"[FacilityService] Loaded {len(self.facilities)} industrial facilities successfully.")

        except Exception as e:
            print(f"[FacilityService] Error loading facilities GeoJSON: {e}")

    def get_nearest_facility(self, lat: float, lon: float) -> Tuple[float, Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
        """Find the nearest industrial facility for a given latitude/longitude.
        
        Returns:
            (distance_to_nearest_industry_km, nearest_facility_id, nearest_facility_type, nearest_facility_name, full_properties)
        """
        if not self.facilities or self.kdtree is None:
            return 999.0, None, "unknown", None, {}

        # 3D lookup via KD-Tree
        qx, qy, qz = latlon_to_cartesian(lat, lon)
        d_chord, idx = self.kdtree.query([qx, qy, qz])

        # Convert chord distance to great circle arc distance in km
        # chord_dist = 2 * sin(theta/2), so theta = 2 * arcsin(chord_dist / 2)
        theta = 2.0 * math.asin(min(1.0, d_chord / 2.0))
        dist_km = EARTH_RADIUS_KM * theta

        nearest_fac = self.facilities[idx]
        return (
            round(dist_km, 4),
            nearest_fac["facility_id"],
            nearest_fac["facility_type"],
            nearest_fac["facility_name"],
            nearest_fac
        )

    def list_facilities(self, facility_type: Optional[str] = None) -> List[FacilityResponse]:
        """List all industrial facilities, optionally filtered by facility_type."""
        results = []
        for fac in self.facilities:
            if facility_type and fac["facility_type"].lower() != facility_type.lower():
                continue
            results.append(FacilityResponse(**fac))
        return results

    def get_facility_by_id(self, facility_id: str) -> Optional[FacilityResponse]:
        """Get facility details by ID."""
        fac = self.facilities_by_id.get(facility_id)
        if fac:
            return FacilityResponse(**fac)
        return None

    def get_facilities_geojson(self, facility_type: Optional[str] = None) -> FacilityCollection:
        """Return GeoJSON FeatureCollection of facilities for map visualization."""
        features = []
        for fac in self.facilities:
            if facility_type and fac["facility_type"].lower() != facility_type.lower():
                continue
            
            feat = FacilityFeature(
                geometry=GeoJSONGeometryPoint(coordinates=[fac["longitude"], fac["latitude"]]),
                properties=FacilityProperties(
                    facility_id=fac["facility_id"],
                    facility_type=fac["facility_type"],
                    facility_name=fac["facility_name"],
                    country=fac["country"],
                    status=fac["status"],
                    capacity=fac["capacity"],
                    coordinate_accuracy=fac["coordinate_accuracy"]
                )
            )
            features.append(feat)

        return FacilityCollection(features=features)


# Global singleton instance
facility_service = FacilityService()
