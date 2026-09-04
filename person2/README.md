# Person 2 — Fire Existence / Anomaly Detector

## Role

Person 2 is the **upstream anomaly detection** module in the satellite-based
industrial fire detection pipeline. It answers the question:

> **"Is there an actual abnormal fire / thermal event?"**

Person 2 does **NOT** classify fire type. The downstream fire-type
classification (INDUSTRIAL / FOREST / OTHER_NATURAL) is handled by
**Person 1**.

```
NASA FIRMS / VIIRS thermal detections
        ↓
   PERSON 2
   Fire existence / anomaly detector
        ↓
   confirmed fire-event detections
        ↓
   PERSON 1
   Fire-type classifier
        ↓
   INDUSTRIAL / FOREST / OTHER_NATURAL
        ↓
   GIS / backend / frontend
```

---

## Detector Architecture

The detector splits incoming VIIRS hotspot detections into two parallel
branches based on spatial proximity to known industrial facilities:

### Branch A — Industrial Facility Context

Hotspot detections within **500 m** of a known industrial facility are
evaluated against that facility's own **historical baseline**.

> **IMPORTANT:** Branch A `branch == "industrial"` means *"this detection
> was evaluated in the context of a known industrial facility."* It does
> **NOT** mean *"this is an industrial fire."* Person 1 makes the final
> fire-type classification.

**Detection logic:**
1. Spatial join — match hotspots to buffered facility polygons (500 m UTM)
2. Facility-day aggregation — daily FRP, hotspot count, centroid, spread
3. Feature engineering — 30-day rolling stats, robust z-score, MAD
4. Minimum-history filter — ≥60 observed days → per-facility model;
   <60 days → pooled model
5. Statistical baseline — robust z-score > 3.0 OR hotspot count > 95th pctl
6. Isolation Forest — per-facility or pooled unsupervised anomaly detection
7. Severity assignment:
   - **HIGH** — both baseline and IF agree
   - **MEDIUM** — either baseline or IF flags
   - **LOW** — neither flags

### Branch B — Open-Area Fallback

Hotspots that do **not** match any known facility are evaluated against
the **regional population** of all open-area detections.

> **IMPORTANT:** Branch B `branch == "open_area"` means *"this detection
> was evaluated outside the industrial-facility context."* It does
> **NOT** mean *"this is a natural fire."*

**Detection logic:**
1. Load unmatched detections from Branch A
2. Feature extraction — FRP, brightness temperatures, scan geometry,
   confidence, day/night, FRP density
3. Regional Isolation Forest — one model on entire open-area population
4. Severity assignment based on IF score percentiles:
   - **HIGH** — IF score in bottom 2% and flagged
   - **MEDIUM** — IF flagged but above 2% threshold
   - **LOW** — not flagged

---

## Input Data

| Source | Description |
|--------|-------------|
| NASA FIRMS VIIRS | VIIRS SNPP 375 m near-real-time thermal detections |
| Facility CSV | Industrial facility locations (lat/lon + facility_id) |

The VIIRS data can be sourced from the NASA FIRMS API or generated
synthetically for testing.

---

## Output Schema

The final Person 2 handoff contains **only** detections where
`fire_event_detected == True`.

| Column | Type | Description |
|--------|------|-------------|
| `detection_id` | string | Stable, deterministic SHA-256 based ID |
| `branch` | string | `"industrial"` or `"open_area"` |
| `facility_id` | string/null | Matched facility ID (Branch A only) |
| `latitude` | float | **Original** VIIRS detection latitude |
| `longitude` | float | **Original** VIIRS detection longitude |
| `date` | string | Detection date (YYYY-MM-DD) |
| `acq_date` | string | FIRMS acquisition date |
| `acq_time` | string | FIRMS acquisition time (HHMM) |
| `frp` | float | Fire Radiative Power (MW) |
| `brightness` | float | VIIRS bright_ti4 (K) |
| `bright_t31` | float | VIIRS bright_ti5 (K) |
| `scan` | float | Scan pixel size |
| `track` | float | Track pixel size |
| `confidence` | string | Detection confidence (low/nominal/high) |
| `satellite` | string | Satellite identifier |
| `instrument` | string | Instrument (VIIRS) |
| `daynight` | string | Day/night flag (D/N) |
| `type` | int | VIIRS detection type |
| `baseline_or_population_reference` | float | Baseline FRP (Branch A) or population median FRP (Branch B) |
| `deviation_ratio` | float | Current FRP / baseline reference |
| `anomaly_score` | float | Isolation Forest decision_function score |
| `fire_event_detected` | bool | Always `True` in handoff output |
| `severity` | string | `HIGH`, `MEDIUM` |
| `contributing_factors` | JSON array | List of factor strings |

### Key Semantics

- **`fire_event_detected`** — `True` means Person 2 has determined that
  this thermal detection represents an **anomalous fire/thermal event**
  relative to the facility baseline (Branch A) or the regional population
  (Branch B). `False` detections are **not** included in the handoff.

- **`severity`** — Reflects detection confidence:
  - `HIGH` = multiple detection methods agree (Branch A) or extreme outlier (Branch B)
  - `MEDIUM` = at least one method flags the detection

- **`anomaly_score`** — The Isolation Forest `decision_function` score.
  More negative = more anomalous. Not directly interpretable as a
  probability.

- **`branch`** ≠ fire type. `"industrial"` means the detection was near
  a facility, not that the fire is industrial. Person 1 makes that call.

---

## Coordinate Preservation

**The output preserves original VIIRS detection coordinates exactly.**

The GeoJSON geometry and the `latitude`/`longitude` columns use the
original values from the FIRMS/VIIRS source data. They are never
replaced with facility centroids, cluster centroids, or any other
derived coordinates.

---

## Configure FIRMS_MAP_KEY

The FIRMS API key is sourced from the environment variable `FIRMS_MAP_KEY`.

```bash
# Linux / macOS
export FIRMS_MAP_KEY="your_key_here"

# Windows (PowerShell)
$env:FIRMS_MAP_KEY = "your_key_here"

# Windows (cmd)
set FIRMS_MAP_KEY=your_key_here
```

Register at: https://firms.modaps.eosdis.nasa.gov/api/area/

If `FIRMS_MAP_KEY` is not set, the pipeline automatically falls back to
synthetic data generation (suitable for testing and demos).

---

## How to Run

### Full Pipeline (synthetic data, no API key needed)

```bash
cd person2
python run_pipeline.py
```

### Full Pipeline with FIRMS API

```bash
export FIRMS_MAP_KEY="your_key"
cd person2
python run_pipeline.py
```

### Skip Data Pull (reuse existing data)

```bash
cd person2
python run_pipeline.py --skip-pull
```

### Evaluation Only

```bash
cd person2
python run_pipeline.py --eval-only
```

### Run Synthetic Evaluation Separately

```bash
cd person2
python evaluation.py
```

---

## Dependencies

All dependencies are listed in the repo-level `requirements.txt`:

- `pandas`
- `numpy` (transitive via pandas)
- `geopandas`
- `shapely`
- `scikit-learn`
- `pyarrow` (for Parquet I/O)
- `requests` (for FIRMS API)
- `pyogrio` (for GeoJSON I/O)

No additional packages are required beyond what is already in the repo.

---

## Handoff Contract with Person 1

Person 1's fire-type classifier (`person1/person1_train_classifier_v0.py`)
expects features including:

```
frp, brightness, bright_t31, scan, track,
distance_to_nearest_industry_km, worldcover_class,
forest_like_landcover, open_vegetation_landcover,
builtup_landcover, bare_sparse_landcover,
water_wetland_landcover, moss_lichen_landcover,
hour, month, dayofyear, sin_hour, cos_hour, sin_month, cos_month,
is_day, nearest_facility_type
```

Person 2's handoff provides:
- `frp`, `brightness` (= bright_ti4), `bright_t31` (= bright_ti5),
  `scan`, `track` — directly from VIIRS
- `acq_date`, `acq_time` — for Person 1 to derive temporal features
- `latitude`, `longitude` — for Person 1 to compute spatial features
  (distance_to_nearest_industry_km, worldcover_class, etc.)

Person 1 is responsible for computing:
- `distance_to_nearest_industry_km` (from GIS layer)
- `worldcover_class` + derived landcover booleans (from ESA WorldCover)
- Temporal features (`hour`, `month`, `sin_hour`, etc.)

Person 2 does **NOT** compute `fire_type`. The downstream pipeline adds:
- `predicted_fire_type` (Person 1's classifier output)

---

## File Structure

```
person2/
├── README.md                   # This file
├── __init__.py                 # Package init
├── region_config.py            # Study region bounding box
├── firms_pull.py               # FIRMS API data pull / synthetic generation
├── data_loader.py              # Load, clean, assign deterministic IDs
├── branch_a_industrial.py      # Industrial facility anomaly detection
├── branch_b_open_area.py       # Open-area fallback anomaly detection
├── evaluation.py               # Synthetic injection evaluation
├── output_schema.py            # Unified output + GeoJSON/CSV export
├── run_pipeline.py             # Full pipeline orchestrator
├── model/                      # Model artifacts (if persisted)
│   └── .gitkeep
└── data/                       # Generated at runtime (not committed)
    ├── viirs_raw.csv
    ├── viirs_clean.parquet
    ├── branch_a_results.parquet
    ├── branch_b_input.parquet
    ├── branch_b_results.parquet
    ├── person2_fire_detections.csv       ← Person 1 handoff
    └── person2_fire_detections.geojson   ← Person 1 handoff
```

---

## Technical Specifications

| Parameter | Value |
|-----------|-------|
| Region | Gujarat Golden Corridor (21.20°N–22.40°N, 72.60°E–73.40°E) |
| Data source | VIIRS SNPP 375 m (NASA FIRMS) |
| Facility buffer | 500 m radius (UTM 42N projection) |
| Minimum history | 60 observed days |
| Rolling window | 30 days |
| Robust z-score threshold | 3.0 |
| Hotspot count percentile | 95th |
| IF contamination | 0.05 |
| IF estimators | 100 |
| Severity levels | HIGH, MEDIUM, LOW |
| detection_id | SHA-256 hash (first 12 hex chars) of acq_date+acq_time+lat+lon+satellite+frp |
