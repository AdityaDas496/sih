import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["facilities_loaded"] > 0


def test_facilities_endpoints():
    # List facilities
    response = client.get("/api/facilities")
    assert response.status_code == 200
    facilities = response.json()
    assert isinstance(facilities, list)
    assert len(facilities) > 0
    
    first_fac_id = facilities[0]["facility_id"]
    
    # Detail facility
    res_detail = client.get(f"/api/facilities/{first_fac_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["facility_id"] == first_fac_id

    # GeoJSON facilities
    res_geojson = client.get("/api/facilities/geojson")
    assert res_geojson.status_code == 200
    geojson_data = res_geojson.json()
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) > 0


def test_detections_endpoints():
    # List detections
    response = client.get("/api/detections")
    assert response.status_code == 200
    detections = response.json()
    assert isinstance(detections, list)
    assert len(detections) > 0
    
    first_event = detections[0]
    first_id = first_event["detection_id"]
    assert first_event["fire_type"] in ["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]
    assert first_event["severity"] in ["HIGH", "MEDIUM", "LOW"]

    # Detail detection
    res_detail = client.get(f"/api/detections/{first_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["detection_id"] == first_id

    # Filtered detections
    res_filter = client.get(f"/api/detections?fire_type={first_event['fire_type']}")
    assert res_filter.status_code == 200
    filtered = res_filter.json()
    assert all(d["fire_type"] == first_event["fire_type"] for d in filtered)


def test_detections_geojson_endpoint():
    response = client.get("/api/detections/geojson")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    
    first_feature = data["features"][0]
    assert first_feature["type"] == "Feature"
    assert first_feature["geometry"]["type"] == "Point"
    assert len(first_feature["geometry"]["coordinates"]) == 2
    assert "fire_type" in first_feature["properties"]
    assert "classification_confidence" in first_feature["properties"]


def test_statistics_endpoint():
    response = client.get("/api/statistics")
    assert response.status_code == 200
    stats = response.json()
    assert "total_detected_events" in stats
    assert "industrial_count" in stats
    assert "forest_count" in stats
    assert "other_natural_count" in stats
    assert stats["total_detected_events"] > 0


def test_classify_endpoint():
    payload = {
        "detection_id": "TEST_DET_999",
        "latitude": 24.7643,
        "longitude": 74.6058,
        "acq_date": "2026-03-15",
        "acq_time": "1430",
        "brightness": 335.5,
        "bright_t31": 298.2,
        "frp": 18.4,
        "scan": 0.4,
        "track": 0.4,
        "confidence": "h",
        "satellite": "SNPP",
        "instrument": "VIIRS",
        "daynight": "D",
        "type": 2,
        "fire_event_detected": True,
        "branch": "industrial",
        "anomaly_score": 0.92
    }
    
    response = client.post("/api/classify", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["detection_id"] == "TEST_DET_999"
    assert result["fire_type"] in ["INDUSTRIAL", "FOREST", "OTHER_NATURAL"]
    assert result["severity"] == "HIGH"
    assert result["classification_confidence"] > 0.0
    assert result["nearest_facility_type"] is not None
    assert result["distance_to_nearest_industry_km"] >= 0.0


def test_classify_endpoint_rejected_if_not_detected():
    payload = {
        "latitude": 24.7643,
        "longitude": 74.6058,
        "acq_date": "2026-03-15",
        "acq_time": "1430",
        "brightness": 300.0,
        "bright_t31": 280.0,
        "frp": 1.0,
        "fire_event_detected": False
    }
    response = client.post("/api/classify", json=payload)
    assert response.status_code == 400
    assert "Skipping record" in response.json()["detail"]


def test_process_batch_endpoint():
    payload = {
        "detections": [
            {
                "detection_id": "BATCH_01",
                "latitude": 21.6813,
                "longitude": 84.0402,
                "acq_date": "2026-03-16",
                "acq_time": "2000",
                "brightness": 312.0,
                "bright_t31": 292.0,
                "frp": 12.0,
                "fire_event_detected": True
            },
            {
                "detection_id": "BATCH_02_REJECTED",
                "latitude": 20.0,
                "longitude": 80.0,
                "acq_date": "2026-03-16",
                "acq_time": "2000",
                "brightness": 290.0,
                "bright_t31": 280.0,
                "frp": 0.5,
                "fire_event_detected": False
            }
        ]
    }
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["total_processed"] == 2
    assert res["successful"] == 1
    assert res["failed"] == 1
    assert res["events"][0]["detection_id"] == "BATCH_01"
