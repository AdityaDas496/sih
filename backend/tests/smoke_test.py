import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_client = TestClient(app)
        cls.client = cls.test_client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.test_client.__exit__(None, None, None)

    def test_01_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["facilities_loaded"] > 0)
        self.assertTrue(data["person1_model_loaded"])

    def test_02_facilities(self):
        res_list = self.client.get("/api/facilities")
        self.assertEqual(res_list.status_code, 200)
        facilities = res_list.json()
        self.assertIsInstance(facilities, list)
        self.assertGreater(len(facilities), 0)

        fac_id = facilities[0]["facility_id"]
        res_detail = self.client.get(f"/api/facilities/{fac_id}")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.json()["facility_id"], fac_id)

        res_geojson = self.client.get("/api/facilities/geojson")
        self.assertEqual(res_geojson.status_code, 200)
        self.assertEqual(res_geojson.json()["type"], "FeatureCollection")

    def test_03_detections(self):
        res_list = self.client.get("/api/detections")
        self.assertEqual(res_list.status_code, 200)
        detections = res_list.json()
        self.assertIsInstance(detections, list)
        self.assertGreater(len(detections), 0)

        first = detections[0]
        self.assertIn(first["fire_type"], ["INDUSTRIAL", "FOREST", "OTHER_NATURAL"])
        self.assertIn(first["severity"], ["HIGH", "MEDIUM", "LOW"])

        res_detail = self.client.get(f"/api/detections/{first['detection_id']}")
        self.assertEqual(res_detail.status_code, 200)

        res_filter = self.client.get(f"/api/detections?fire_type={first['fire_type']}")
        self.assertEqual(res_filter.status_code, 200)
        for item in res_filter.json():
            self.assertEqual(item["fire_type"], first["fire_type"])

    def test_04_detections_geojson(self):
        response = self.client.get("/api/detections/geojson")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertGreater(len(data["features"]), 0)

        feat = data["features"][0]
        self.assertEqual(feat["geometry"]["type"], "Point")
        self.assertEqual(len(feat["geometry"]["coordinates"]), 2)
        self.assertIn("fire_type", feat["properties"])
        self.assertIn("classification_confidence", feat["properties"])

    def test_05_statistics(self):
        response = self.client.get("/api/statistics")
        self.assertEqual(response.status_code, 200)
        stats = response.json()
        self.assertIn("total_detected_events", stats)
        self.assertIn("industrial_count", stats)
        self.assertIn("forest_count", stats)
        self.assertIn("other_natural_count", stats)
        self.assertGreater(stats["total_detected_events"], 0)

    def test_06_classify(self):
        payload = {
            "detection_id": "TEST_SMOKE_001",
            "latitude": 24.7643,
            "longitude": 74.6058,
            "acq_date": "2026-03-15",
            "acq_time": "1430",
            "brightness": 345.5,
            "bright_t31": 298.2,
            "frp": 25.4,
            "scan": 0.4,
            "track": 0.4,
            "confidence": "h",
            "satellite": "SNPP",
            "instrument": "VIIRS",
            "daynight": "D",
            "type": 2,
            "fire_event_detected": True,
            "branch": "industrial",
            "anomaly_score": 0.95
        }
        res = self.client.post("/api/classify", json=payload)
        self.assertEqual(res.status_code, 200)
        result = res.json()
        self.assertEqual(result["detection_id"], "TEST_SMOKE_001")
        self.assertIn(result["fire_type"], ["INDUSTRIAL", "FOREST", "OTHER_NATURAL"])
        self.assertEqual(result["severity"], "HIGH")

    def test_07_classify_rejected(self):
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
        res = self.client.post("/api/classify", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_08_process_batch(self):
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
        res = self.client.post("/api/process", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_processed"], 2)
        self.assertEqual(data["successful"], 1)
        self.assertEqual(data["failed"], 1)


if __name__ == "__main__":
    unittest.main()
