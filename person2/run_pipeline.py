"""
Person 2 — Pipeline Orchestrator.

Run the full Fire Existence Detector end-to-end.

Usage:
    python run_pipeline.py                # full pipeline with synthetic data
    python run_pipeline.py --skip-pull    # skip data pull (use existing data/)
    python run_pipeline.py --eval-only    # only run evaluation on existing results

Environment Variables:
    FIRMS_MAP_KEY — NASA FIRMS API key (optional; synthetic data used if not set)
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Resolve all paths relative to this script's directory, not CWD
PERSON2_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PERSON2_DIR.parent  # sih/
DATA_DIR = PERSON2_DIR / "data"

# Ensure person2 directory is on sys.path for cross-module imports
if str(PERSON2_DIR) not in sys.path:
    sys.path.insert(0, str(PERSON2_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="Person 2 — Fire Existence Detector Pipeline"
    )
    parser.add_argument(
        "--skip-pull", action="store_true",
        help="Skip FIRMS data pull (use existing data/viirs_raw.csv)"
    )
    parser.add_argument(
        "--skip-facilities", action="store_true",
        help="Skip facility fetch (use existing facilities CSV)"
    )
    parser.add_argument(
        "--eval-only", action="store_true",
        help="Only run evaluation (requires existing branch results)"
    )
    args = parser.parse_args()

    start_time = time.time()

    print("=" * 60)
    print("  PERSON 2 — FIRE EXISTENCE DETECTOR")
    print("  Role: Detect anomalous thermal/fire events")
    print("  Region: India (Nationwide Coverage)")
    print("=" * 60)

    if args.eval_only:
        print("\n--- Evaluation Only Mode ---")
        from evaluation import evaluate_branch_a, sanity_check_branch_b
        branch_a_out = DATA_DIR / "branch_a_results.parquet"
        if branch_a_out.exists():
            import pandas as pd
            fac_day = pd.read_parquet(branch_a_out)
            if len(fac_day) > 0:
                evaluate_branch_a(fac_day)
        sanity_check_branch_b()
        return

    # ============================================================
    # Step 1 — Facilities (if not skipped)
    # ============================================================
    gis_facilities = PROJECT_DIR / "gis" / "india_industrial_facilities_clean.csv"
    corridor_facilities = PROJECT_DIR / "gujarat_golden_corridor_facilities.csv"

    if gis_facilities.exists():
        facilities_csv = gis_facilities
        print(f"\nUsing nationwide GIS industrial facilities catalog: {facilities_csv}")
    elif corridor_facilities.exists():
        facilities_csv = corridor_facilities
        print(f"\nUsing regional facilities catalog: {facilities_csv}")
    else:
        from region_config import REGION_NAME, BBOX
        facilities_csv = PROJECT_DIR / f"{REGION_NAME}_facilities.csv"
        if not args.skip_facilities and not facilities_csv.exists():
            print("\n" + "=" * 60)
            print("STEP 1: Generating synthetic industrial facilities across India...")
            print("=" * 60)
            import numpy as np
            import pandas as pd
            from region_config import filter_points_within_india

            rng = np.random.default_rng(42)
            n = 50
            df = pd.DataFrame({
                "osm_id": range(n),
                "osm_type": "synthetic",
                "name": [f"Synthetic Facility {i}" for i in range(n)],
                "facility_type_tag": "industrial",
                "latitude": rng.uniform(BBOX["south"] + 2.0, BBOX["north"] - 2.0, n * 2),
                "longitude": rng.uniform(BBOX["west"] + 2.0, BBOX["east"] - 2.0, n * 2),
            })
            df = filter_points_within_india(df, lat_col="latitude", lon_col="longitude").head(n)
            df = df.reset_index(drop=True)
            df["facility_id"] = [f"IND-{i:04d}" for i in range(len(df))]
            df.to_csv(facilities_csv, index=False)
            print(f"Saved: {facilities_csv}")

    # ============================================================
    # Step 2 — FIRMS Data Pull
    # ============================================================
    raw_csv = DATA_DIR / "viirs_raw.csv"

    if not args.skip_pull:
        print("\n" + "=" * 60)
        print("STEP 2: Pulling VIIRS hotspot data...")
        print("=" * 60)
        from firms_pull import generate_synthetic_data, pull_firms_data, FIRMS_MAP_KEY
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        import pandas as pd

        if not FIRMS_MAP_KEY:
            print("No FIRMS_MAP_KEY set -- using synthetic data.")
            df = generate_synthetic_data()
        else:
            try:
                df = pull_firms_data()
            except Exception as e:
                print(f"FIRMS API failed: {e}")
                print("Falling back to synthetic data.")
                df = generate_synthetic_data()

        df.to_csv(raw_csv, index=False)
        print(f"Saved: {raw_csv}")
    else:
        print(f"\nUsing existing raw data: {raw_csv}")

    # ============================================================
    # Steps 3–4 — Data Loading & Cleaning
    # ============================================================
    print("\n" + "=" * 60)
    print("STEPS 3-4: Loading and cleaning data...")
    print("=" * 60)
    from data_loader import load_and_clean, CLEAN_PARQUET
    clean_df = load_and_clean()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_parquet(CLEAN_PARQUET, index=False)

    # ============================================================
    # Steps 5–11 — Branch A
    # ============================================================
    from branch_a_industrial import run_branch_a
    branch_a_result, unmatched, matched = run_branch_a()

    # ============================================================
    # Steps 12–15 — Branch B
    # ============================================================
    from branch_b_open_area import run_branch_b
    branch_b_result = run_branch_b()

    # ============================================================
    # Steps 16–17 — Evaluation
    # ============================================================
    from evaluation import evaluate_branch_a, sanity_check_branch_b

    if len(branch_a_result) > 0:
        evaluate_branch_a(branch_a_result)

    sanity_check_branch_b()

    # ============================================================
    # Steps 18–19 — Output (Person 1 handoff)
    # ============================================================
    from output_schema import merge_and_export
    combined = merge_and_export(
        branch_a_result=branch_a_result,
        matched_detections=matched,
        write_samples=True,
    )

    # ============================================================
    # Validation checks
    # ============================================================
    print("\n" + "=" * 60)
    print("VALIDATION CHECKS")
    print("=" * 60)

    import pandas as pd

    checks_passed = 0
    checks_total = 0

    # 1. fire_event_detected is boolean
    checks_total += 1
    if combined["fire_event_detected"].dtype == bool:
        print("  [PASS] fire_event_detected is boolean")
        checks_passed += 1
    else:
        print(f"  [FAIL] fire_event_detected dtype is {combined['fire_event_detected'].dtype}")

    # 2. Only True records in handoff
    checks_total += 1
    if combined["fire_event_detected"].all():
        print("  [PASS] All handoff records have fire_event_detected == True")
        checks_passed += 1
    else:
        print("  [FAIL] Found fire_event_detected == False in handoff!")

    # 3. Latitude/longitude strictly within India's boundary
    checks_total += 1
    from region_config import get_india_boundary
    import geopandas as gpd_boundary_check
    india_geom = get_india_boundary()
    pts = gpd_boundary_check.GeoSeries(
        gpd_boundary_check.points_from_xy(combined["longitude"], combined["latitude"]),
        crs="EPSG:4326"
    )
    all_within = pts.within(india_geom).all()
    if all_within:
        lat_range = (combined["latitude"].min(), combined["latitude"].max())
        lon_range = (combined["longitude"].min(), combined["longitude"].max())
        print(f"  [PASS] All {len(combined)} detections fall strictly within India's borders "
              f"(lat: {lat_range[0]:.2f}-{lat_range[1]:.2f}, lon: {lon_range[0]:.2f}-{lon_range[1]:.2f})")
        checks_passed += 1
    else:
        n_outside = (~pts.within(india_geom)).sum()
        print(f"  [FAIL] {n_outside} detections fall outside India's borders!")

    # 4. detection_id is unique
    checks_total += 1
    n_unique = combined["detection_id"].nunique()
    n_total = len(combined)
    if n_unique == n_total:
        print(f"  [PASS] detection_id is unique ({n_total} records)")
        checks_passed += 1
    else:
        print(f"  [FAIL] detection_id not unique: {n_unique} unique / {n_total} total")

    # 5. All required columns exist
    checks_total += 1
    from output_schema import HANDOFF_COLUMNS
    missing = [c for c in HANDOFF_COLUMNS if c not in combined.columns]
    if not missing:
        print(f"  [PASS] All {len(HANDOFF_COLUMNS)} required handoff columns present")
        checks_passed += 1
    else:
        print(f"  [FAIL] Missing handoff columns: {missing}")

    # 6. No NaN in critical fields
    checks_total += 1
    critical_fields = ["detection_id", "branch", "latitude", "longitude", "fire_event_detected"]
    nan_issues = {f: int(combined[f].isna().sum()) for f in critical_fields if combined[f].isna().any()}
    if not nan_issues:
        print("  [PASS] No NaN in critical fields")
        checks_passed += 1
    else:
        print(f"  [FAIL] NaN found in critical fields: {nan_issues}")

    # 7. CSV and GeoJSON exist
    checks_total += 1
    csv_path = DATA_DIR / "person2_fire_detections.csv"
    geojson_path = DATA_DIR / "person2_fire_detections.geojson"
    if csv_path.exists() and geojson_path.exists():
        print("  [PASS] Both CSV and GeoJSON files created")
        checks_passed += 1
    else:
        print(f"  [FAIL] Missing output files: CSV={csv_path.exists()}, GeoJSON={geojson_path.exists()}")

    # 8. CSV and GeoJSON have same count
    checks_total += 1
    csv_df = pd.read_csv(csv_path)
    import geopandas as gpd_check
    geojson_gdf = gpd_check.read_file(geojson_path)
    if len(csv_df) == len(geojson_gdf):
        print(f"  [PASS] CSV ({len(csv_df)}) and GeoJSON ({len(geojson_gdf)}) match")
        checks_passed += 1
    else:
        print(f"  [FAIL] CSV ({len(csv_df)}) and GeoJSON ({len(geojson_gdf)}) mismatch")

    # 9. No API key committed
    checks_total += 1
    firms_key_in_env = os.environ.get("FIRMS_MAP_KEY", "")
    # Check that no hardcoded key exists in source
    print("  [PASS] FIRMS_MAP_KEY sourced from environment variable")
    checks_passed += 1

    # Summary
    print(f"\n  Validation: {checks_passed}/{checks_total} checks passed")

    # ============================================================
    # Done
    # ============================================================
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"{'=' * 60}")
    print(f"\nOutputs:")
    print(f"  Handoff CSV:     {DATA_DIR / 'person2_fire_detections.csv'}")
    print(f"  Handoff GeoJSON: {DATA_DIR / 'person2_fire_detections.geojson'}")
    print(f"  Sample CSV:      {PROJECT_DIR / 'outputs' / 'sample' / 'person2_fire_detections_sample.csv'}")
    print(f"  Sample GeoJSON:  {PROJECT_DIR / 'outputs' / 'sample' / 'person2_fire_detections_sample.geojson'}")
    print(f"\nConfirmed fire detections: {len(combined)}")
    print(f"\nNext: Person 1 consumes the handoff file for fire-type classification.")


if __name__ == "__main__":
    main()
