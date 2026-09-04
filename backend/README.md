# Satellite Industrial Fire Detection API & Integration Layer

Backend API and integration layer connecting **Person 2 (Fire Existence Detector)**, **Person 1 (Fire Type Classifier)**, and the **Frontend GIS / Map Visualization Interface**.

Built with **FastAPI**, **Pydantic v2**, **scikit-learn**, **scipy (cKDTree)**, and **Pandas**.

---

## 🏛️ System Architecture

```
                                  [ Satellite VIIRS / FIRMS Data ]
                                                 │
                                                 ▼
                             [ Person 2: Fire Existence Detector ]
                                                 │
                                                 │ (fire_event_detected == True)
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │          Backend API Layer            │
                             ├───────────────────────────────────────┤
                             │  1. Ingestion & Validation            │
                             │  2. Industry Spatial Lookup (KD-Tree) │
                             │  3. WorldCover Landcover Sampling     │
                             │  4. Temporal Feature Transformations  │
                             └───────────────────────────────────────┘
                                                 │
                                                 ▼
                             [ Person 1: Fire Type Classifier ML ]
                                                 │
                                                 ▼
                              Canonical Output Normalization:
                        INDUSTRIAL | FOREST | OTHER_NATURAL
                                                 │
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │       FastAPI REST Endpoints          │
                             ├───────────────────────────────────────┤
                             │  • /health                            │
                             │  • /api/detections                    │
                             │  • /api/detections/geojson            │
                             │  • /api/facilities                    │
                             │  • /api/statistics                    │
                             │  • /api/classify                      │
                             │  • /api/process                       │
                             └───────────────────────────────────────┘
                                                 │
                                                 ▼
                             [ Frontend GIS Map & Visual Dashboards ]
```

---

## 🚀 Setup & Quick Start

### 1. Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt`:
  - `fastapi`
  - `uvicorn`
  - `pydantic`
  - `pandas`
  - `scikit-learn`
  - `joblib`
  - `scipy`
  - `httpx`

### 2. Installation

From the repository root:

```bash
# Navigate to backend or run directly from repository root
cd backend
pip install -r requirements.txt
```

### 3. Environment Variables (Optional Configuration)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `PERSON1_MODEL_PATH` | `<root>/person1/model/person1_fire_type_classifier_v0.joblib` | Path to trained Person 1 ML model |
| `GIS_FACILITIES_PATH` | `<root>/gis/india_industrial_facilities.geojson` | Path to industrial facilities GeoJSON |
| `SAMPLE_PREDICTIONS_PATH` | `<root>/outputs/sample/person1_fire_type_classification_predictions_v0.csv` | Sample pre-classified dataset |
| `WORLDCOVER_TILES_DIR` | `<root>/worldcover_tiles` | Directory containing local WorldCover TIF tiles |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173,*` | Allowed CORS origins |

### 4. Running the Server

Run from the repository root:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or from inside `backend/`:

```bash
python app/main.py
```

Open your browser to:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 API Endpoints Reference

### 1. `GET /health`
Returns backend health status, loaded facility count, and ML model status.

**Response Example:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "person1_model_loaded": true,
  "facilities_loaded": 1118,
  "cached_detections_count": 20102
}
```

---

### 2. `GET /api/detections`
Retrieve list of canonical classified fire events with filtering and pagination.

**Query Parameters:**
- `fire_type`: Filter by `INDUSTRIAL`, `FOREST`, or `OTHER_NATURAL`
- `severity`: Filter by `HIGH`, `MEDIUM`, or `LOW`
- `branch`: Filter by Person 2 detector branch (`industrial`, `forest`, `general`)
- `facility_type`: Filter by nearest facility type (`steel`, `cement`, `coal_power`)
- `min_confidence`: Minimum prediction confidence (0.0 to 1.0)
- `date_from`: `YYYY-MM-DD`
- `date_to`: `YYYY-MM-DD`
- `limit`: Default `500` (max 10000)
- `offset`: Default `0`

**Response Example:**
```json
[
  {
    "detection_id": "DET_00001",
    "latitude": 24.7643,
    "longitude": 74.6058,
    "acq_date": "2025-12-09",
    "acq_time": "2001",
    "fire_type": "INDUSTRIAL",
    "classification_confidence": 1.0,
    "severity": "LOW",
    "branch": "industrial",
    "frp": 1.62,
    "brightness": 304.73,
    "bright_t31": 290.12,
    "confidence": "n",
    "satellite": "SNPP",
    "instrument": "VIIRS",
    "distance_to_nearest_industry_km": 0.399,
    "nearest_facility_id": "L100000102178",
    "nearest_facility_type": "coal_power",
    "nearest_facility_name": "Rawan Cement power station",
    "worldcover_class": 50,
    "contributing_factors": "Nearest facility: Rawan Cement power station; FRP: 1.62 MW",
    "anomaly_score": 1.0,
    "fire_event_detected": true
  }
]
```

---

### 3. `GET /api/detections/geojson`
Returns a map-ready **GeoJSON FeatureCollection** for spatial visualization.

> [!IMPORTANT]
> Feature geometry strictly uses original satellite VIIRS `[longitude, latitude]` coordinates (`Point`), preserving exact satellite event location.

**Response Example:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [74.6058, 24.7643]
      },
      "properties": {
        "detection_id": "DET_00001",
        "fire_type": "INDUSTRIAL",
        "classification_confidence": 1.0,
        "severity": "LOW",
        "branch": "industrial",
        "frp": 1.62,
        "brightness": 304.73,
        "bright_t31": 290.12,
        "acq_date": "2025-12-09",
        "acq_time": "2001",
        "distance_to_nearest_industry_km": 0.399,
        "nearest_facility_id": "L100000102178",
        "nearest_facility_type": "coal_power",
        "nearest_facility_name": "Rawan Cement power station"
      }
    }
  ]
}
```

---

### 4. `GET /api/detections/{detection_id}`
Returns details for a single classified detection event by ID.

---

### 5. `GET /api/facilities` & `GET /api/facilities/geojson`
Retrieves industrial facility overlay data (Steel, Cement, Coal Power plants).

---

### 6. `GET /api/statistics`
Returns summary metrics for dashboard widgets.

**Response Example:**
```json
{
  "total_detected_events": 20102,
  "industrial_count": 9840,
  "forest_count": 6432,
  "other_natural_count": 3830,
  "high_severity_count": 4120,
  "medium_severity_count": 8950,
  "low_severity_count": 7032,
  "by_facility_type": {
    "cement": 7820,
    "coal_power": 6410,
    "steel": 5872
  },
  "by_branch": {
    "industrial": 9840,
    "forest": 6432,
    "other_natural": 3830
  }
}
```

---

### 7. `POST /api/classify`
Classifies a single Person 2 detection payload in real time.

**Request Payload Example:**
```json
{
  "detection_id": "REALTIME_001",
  "latitude": 24.7643,
  "longitude": 74.6058,
  "acq_date": "2026-09-04",
  "acq_time": "1430",
  "brightness": 345.5,
  "bright_t31": 298.2,
  "frp": 22.4,
  "confidence": "h",
  "satellite": "SNPP",
  "instrument": "VIIRS",
  "daynight": "D",
  "type": 2,
  "fire_event_detected": true,
  "branch": "industrial",
  "anomaly_score": 0.95
}
```

---

### 8. `POST /api/process`
Ingests a batch of Person 2 confirmed detections, filtering out any records where `fire_event_detected == False`.

---

## 🤝 Person 2 → Backend Contract

Person 2 delivers thermal detection events containing VIIRS satellite fields plus detector anomaly fields:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `fire_event_detected` | `bool` | Must be `true` for processing (records with `false` are filtered out) |
| `latitude` | `float` | VIIRS event latitude |
| `longitude` | `float` | VIIRS event longitude |
| `acq_date` | `str` | Acquisition date (`YYYY-MM-DD`) |
| `acq_time` | `str` | Acquisition time (`HHMM`) |
| `brightness` | `float` | VIIRS Channel 21/22 brightness temperature (K) |
| `bright_t31` | `float` | VIIRS Channel 31 brightness temperature (K) |
| `frp` | `float` | Fire Radiative Power (MW) |
| `branch` | `str` | Person 2 detector branch (`industrial`, `forest`, `general`) |
| `anomaly_score` | `float` | Thermal anomaly confidence score |

---

## 🧠 Person 1 Model Integration Method

1. **Saved Artifact**: Loads `person1/model/person1_fire_type_classifier_v0.joblib` containing:
   - `model`: Trained `RandomForestClassifier`
   - `feature_columns`: List of expected one-hot feature column names
   - `numeric_medians`: Training set medians for NaN imputation
   - `classes`: Raw class names (`forest_proxy`, `industrial_proxy`, `other_natural_proxy`)
2. **Feature Engineering**:
   - Temporal sine/cosine transformations (`sin_hour`, `cos_hour`, `sin_month`, `cos_month`, `is_day`, `dayofyear`)
   - Industry lookup via 3D KD-Tree -> `distance_to_nearest_industry_km` & `nearest_facility_type`
   - ESA WorldCover sampling -> `worldcover_class` and 6 landcover binary flags
3. **Normalizing Model Output**:
   - `industrial_proxy` -> `INDUSTRIAL`
   - `forest_proxy` -> `FOREST`
   - `other_natural_proxy` -> `OTHER_NATURAL`
4. **Model Confidence**:
   - `classification_confidence` = max prediction probability from `predict_proba()`

---

## 🧪 Testing & Verification

Run automated integration test suite:

```bash
python backend/tests/smoke_test.py
```

Expected output:
```
Ran 8 tests in 2.600s
OK
```
