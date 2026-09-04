"""
Person 2 — Output Schema: Merge Branch A + Branch B into a unified
handoff format for Person 1.

CRITICAL CONTRACT:
- Only detections with fire_event_detected == True are included in the
  final handoff file.
- Original VIIRS coordinates (latitude, longitude) are preserved exactly.
- All required handoff columns are present. Columns that are not
  applicable for a particular branch use safe null values.
- detection_id is stable and deterministic.
- GeoJSON geometry uses the original (longitude, latitude).

Output:
    data/person2_fire_detections.csv
    data/person2_fire_detections.geojson
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PERSON2_DIR.parent  # sih/
DATA_DIR = PERSON2_DIR / "data"
BRANCH_A_OUT = DATA_DIR / "branch_a_results.parquet"
BRANCH_B_OUT = DATA_DIR / "branch_b_results.parquet"
CLEAN_PARQUET = DATA_DIR / "viirs_clean.parquet"

# Handoff output paths
OUTPUT_CSV = DATA_DIR / "person2_fire_detections.csv"
OUTPUT_GEOJSON = DATA_DIR / "person2_fire_detections.geojson"

# Sample output paths
SAMPLE_DIR = PROJECT_DIR / "outputs" / "sample"
SAMPLE_CSV = SAMPLE_DIR / "person2_fire_detections_sample.csv"
SAMPLE_GEOJSON = SAMPLE_DIR / "person2_fire_detections_sample.geojson"

# The full required handoff columns
HANDOFF_COLUMNS = [
    "detection_id",
    "branch",
    "facility_id",
    "latitude",
    "longitude",
    "date",
    "acq_date",
    "acq_time",
    "frp",
    "brightness",
    "bright_t31",
    "scan",
    "track",
    "confidence",
    "satellite",
    "instrument",
    "daynight",
    "type",
    "baseline_or_population_reference",
    "deviation_ratio",
    "anomaly_score",
    "fire_event_detected",
    "severity",
    "contributing_factors",
]


def _safe_list(val):
    """Convert contributing_factors to a JSON-serializable list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _safe_json_str(val):
    """Convert contributing_factors list to JSON string for CSV/GeoJSON."""
    lst = _safe_list(val)
    return json.dumps(lst)


def format_branch_a(
    branch_a_result: pd.DataFrame,
    matched_detections: pd.DataFrame,
) -> pd.DataFrame:
    """
    Format Branch A results into the unified handoff schema.

    CRITICAL: We join facility-day anomaly results back to the original
    per-detection records so each output row has the original VIIRS
    coordinates, NOT facility centroids.
    """
    if len(branch_a_result) == 0 or len(matched_detections) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    # Get flagged facility-days (fire_event_detected == True)
    flagged_days = branch_a_result[
        branch_a_result["has_obs"] & branch_a_result["fire_event_detected"]
    ][["facility_id", "date", "severity", "fire_event_detected",
       "if_score", "frp_rolling_median_30d", "frp_mean",
       "contributing_factors", "baseline_anomaly", "if_anomaly"]].copy()

    if len(flagged_days) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    flagged_days["date"] = pd.to_datetime(flagged_days["date"])

    # Ensure matched_detections has a proper date column
    det = matched_detections.copy()
    det["date"] = pd.to_datetime(det["date"])

    # Join: match each detection back to its facility-day anomaly result
    merged = det.merge(
        flagged_days,
        on=["facility_id", "date"],
        how="inner",
        suffixes=("", "_facday"),
    )

    if len(merged) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    # Compute deviation ratio per detection
    baseline_ref = merged["frp_rolling_median_30d"].replace(0, np.nan)
    deviation = np.where(
        baseline_ref.notna() & (baseline_ref > 0),
        merged["frp"] / baseline_ref,
        np.nan,
    )

    # Map VIIRS column names to handoff names
    # VIIRS bright_ti4 → handoff "brightness"
    # VIIRS bright_ti5 → handoff "bright_t31"
    out = pd.DataFrame({
        "detection_id": merged["detection_id"],
        "branch": "industrial",
        "facility_id": merged["facility_id"],
        "latitude": merged["latitude"],        # ORIGINAL VIIRS coordinates
        "longitude": merged["longitude"],       # ORIGINAL VIIRS coordinates
        "date": merged["date"].dt.strftime("%Y-%m-%d"),
        "acq_date": merged.get("acq_date", merged["date"].dt.strftime("%Y-%m-%d")),
        "acq_time": merged.get("acq_time", pd.Series("", index=merged.index)),
        "frp": merged["frp"],
        "brightness": merged.get("bright_ti4", np.nan),
        "bright_t31": merged.get("bright_ti5", np.nan),
        "scan": merged["scan"],
        "track": merged["track"],
        "confidence": merged.get("confidence_str",
                                 merged.get("confidence", "")),
        "satellite": merged.get("satellite", "N"),
        "instrument": merged.get("instrument", "VIIRS"),
        "daynight": merged.get("daynight", ""),
        "type": merged.get("type", np.nan),
        "baseline_or_population_reference": merged["frp_rolling_median_30d"],
        "deviation_ratio": deviation,
        "anomaly_score": merged["if_score"],
        "fire_event_detected": True,
        "severity": merged["severity"],
        "contributing_factors": merged["contributing_factors"].apply(_safe_list),
    })

    return out


def format_branch_b(df: pd.DataFrame) -> pd.DataFrame:
    """
    Format Branch B results into the unified handoff schema.

    Only includes detections where fire_event_detected == True.
    Original VIIRS coordinates are already preserved in Branch B.
    """
    if len(df) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    # Only keep flagged detections
    flagged = df[df["fire_event_detected"]].copy()

    if len(flagged) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    # Population-level reference for Branch B
    population_median = df["frp"].median()

    out = pd.DataFrame({
        "detection_id": flagged["detection_id"],
        "branch": "open_area",
        "facility_id": None,  # no facility for open-area
        "latitude": flagged["latitude"],        # ORIGINAL VIIRS coordinates
        "longitude": flagged["longitude"],       # ORIGINAL VIIRS coordinates
        "date": pd.to_datetime(flagged["date"]).dt.strftime("%Y-%m-%d"),
        "acq_date": flagged.get("acq_date",
                                pd.to_datetime(flagged["date"]).dt.strftime("%Y-%m-%d")),
        "acq_time": flagged.get("acq_time", pd.Series("", index=flagged.index)),
        "frp": flagged["frp"],
        "brightness": flagged.get("bright_ti4", np.nan),
        "bright_t31": flagged.get("bright_ti5", np.nan),
        "scan": flagged["scan"],
        "track": flagged["track"],
        "confidence": flagged.get("confidence_str",
                                  flagged.get("confidence", "")),
        "satellite": flagged.get("satellite", "N"),
        "instrument": flagged.get("instrument", "VIIRS"),
        "daynight": flagged.get("daynight", ""),
        "type": flagged.get("type", np.nan),
        "baseline_or_population_reference": population_median,
        "deviation_ratio": flagged["frp"] / max(population_median, 0.1),
        "anomaly_score": flagged.get("if_score", np.nan),
        "fire_event_detected": True,
        "severity": flagged["severity"],
        "contributing_factors": flagged["contributing_factors"].apply(_safe_list),
    })

    return out


def merge_and_export(
    branch_a_result: pd.DataFrame = None,
    matched_detections: pd.DataFrame = None,
    write_samples: bool = True,
):
    """
    Merge both branches and export to GeoJSON + CSV.

    Only fire_event_detected == True records are included in the
    final handoff.
    """
    print("\n" + "=" * 60)
    print("OUTPUT -- Merging and Exporting (Person 2 Handoff)")
    print("=" * 60)

    dfs = []

    # Branch A
    if branch_a_result is not None and len(branch_a_result) > 0:
        if matched_detections is not None and len(matched_detections) > 0:
            a_formatted = format_branch_a(branch_a_result, matched_detections)
            dfs.append(a_formatted)
            print(f"  Branch A fire detections: {len(a_formatted)}")
    elif BRANCH_A_OUT.exists():
        branch_a = pd.read_parquet(BRANCH_A_OUT)
        # If we don't have matched_detections, try loading from clean
        if CLEAN_PARQUET.exists() and len(branch_a) > 0:
            print("  WARNING: No matched_detections available. Branch A output "
                  "may use facility-day centroids instead of per-detection coords.")
            # Fallback: format from facility-day data (limited accuracy)
            a_fallback = _format_branch_a_fallback(branch_a)
            if len(a_fallback) > 0:
                dfs.append(a_fallback)
                print(f"  Branch A fire detections (fallback): {len(a_fallback)}")

    # Branch B
    if BRANCH_B_OUT.exists():
        branch_b = pd.read_parquet(BRANCH_B_OUT)
        if len(branch_b) > 0:
            b_formatted = format_branch_b(branch_b)
            dfs.append(b_formatted)
            print(f"  Branch B fire detections: {len(b_formatted)}")
    else:
        print("  Branch B results not found -- skipping.")

    if not dfs:
        print("ERROR: No fire detections from either branch. Nothing to export.")
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    combined = pd.concat(dfs, ignore_index=True)

    # Ensure all handoff columns exist
    for col in HANDOFF_COLUMNS:
        if col not in combined.columns:
            combined[col] = None

    # Reorder to match handoff spec
    combined = combined[HANDOFF_COLUMNS].copy()

    # Ensure fire_event_detected is boolean
    combined["fire_event_detected"] = combined["fire_event_detected"].astype(bool)

    # Verify all are True (we only export confirmed detections)
    assert combined["fire_event_detected"].all(), \
        "BUG: Non-fire detections found in handoff output!"

    # Verify detection_id uniqueness
    n_dups = combined["detection_id"].duplicated().sum()
    if n_dups > 0:
        print(f"  WARNING: {n_dups} duplicate detection_ids found. De-duplicating...")
        combined = combined.drop_duplicates(subset=["detection_id"], keep="first")

    print(f"\n  Total confirmed fire detections: {len(combined)}")
    print(f"  By branch: {combined['branch'].value_counts().to_dict()}")
    print(f"  By severity: {combined['severity'].value_counts().to_dict()}")

    # --- Export CSV ---
    csv_out = combined.copy()
    csv_out["contributing_factors"] = csv_out["contributing_factors"].apply(_safe_json_str)
    # Handle NaN in type column for clean CSV
    csv_out["type"] = csv_out["type"].fillna(-1).astype(int).replace(-1, "")

    csv_out.to_csv(OUTPUT_CSV, index=False)
    print(f"\n  Saved CSV: {OUTPUT_CSV}")

    # --- Export GeoJSON ---
    geo_df = combined.dropna(subset=["latitude", "longitude"]).copy()
    geo_df = geo_df[
        (geo_df["latitude"] != 0) & (geo_df["longitude"] != 0)
    ]

    if len(geo_df) > 0:
        geo_df["contributing_factors"] = geo_df["contributing_factors"].apply(_safe_json_str)
        # Convert date to string for GeoJSON serialization
        geo_df["date"] = geo_df["date"].astype(str)
        geo_df["acq_date"] = geo_df["acq_date"].astype(str)
        # Replace NaN with None for clean GeoJSON
        geo_df = geo_df.fillna("")

        gdf = gpd.GeoDataFrame(
            geo_df,
            geometry=[
                Point(xy) for xy in zip(
                    geo_df["longitude"].astype(float),
                    geo_df["latitude"].astype(float),
                )
            ],
            crs="EPSG:4326",
        )
        gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
        print(f"  Saved GeoJSON: {OUTPUT_GEOJSON}")
    else:
        print("  WARNING: No valid coordinates for GeoJSON export.")

    # --- Write sample files ---
    if write_samples and len(combined) > 0:
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        sample = combined.head(min(20, len(combined))).copy()

        sample_csv = sample.copy()
        sample_csv["contributing_factors"] = sample_csv["contributing_factors"].apply(_safe_json_str)
        sample_csv["type"] = sample_csv["type"].fillna(-1)
        sample_csv.to_csv(SAMPLE_CSV, index=False)
        print(f"  Saved sample CSV: {SAMPLE_CSV}")

        sample_geo = sample.dropna(subset=["latitude", "longitude"]).copy()
        if len(sample_geo) > 0:
            sample_geo["contributing_factors"] = sample_geo["contributing_factors"].apply(_safe_json_str)
            sample_geo["date"] = sample_geo["date"].astype(str)
            sample_geo["acq_date"] = sample_geo["acq_date"].astype(str)
            sample_geo = sample_geo.fillna("")
            sample_gdf = gpd.GeoDataFrame(
                sample_geo,
                geometry=[
                    Point(xy) for xy in zip(
                        sample_geo["longitude"].astype(float),
                        sample_geo["latitude"].astype(float),
                    )
                ],
                crs="EPSG:4326",
            )
            sample_gdf.to_file(SAMPLE_GEOJSON, driver="GeoJSON")
            print(f"  Saved sample GeoJSON: {SAMPLE_GEOJSON}")

    # --- Print sample output ---
    print("\n  Sample handoff records (first 5):")
    for _, row in combined.head(5).iterrows():
        print(f"    {row['detection_id']}: branch={row['branch']} | "
              f"lat={row['latitude']}, lon={row['longitude']} | "
              f"FRP={row['frp']} | severity={row['severity']} | "
              f"factors={row['contributing_factors']}")

    return combined


def _format_branch_a_fallback(branch_a: pd.DataFrame) -> pd.DataFrame:
    """
    Fallback formatter when matched_detections aren't available.
    Uses facility-day centroids (less accurate but functional).
    """
    if len(branch_a) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    obs = branch_a[branch_a["has_obs"] & branch_a["fire_event_detected"]].copy()
    if len(obs) == 0:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    baseline_ref = obs.get("frp_rolling_median_30d", pd.Series(np.nan, index=obs.index))

    out = pd.DataFrame({
        "detection_id": obs["facility_id"].astype(str) + "_" + obs["date"].astype(str),
        "branch": "industrial",
        "facility_id": obs["facility_id"],
        "latitude": obs.get("centroid_lat", np.nan),
        "longitude": obs.get("centroid_lon", np.nan),
        "date": obs["date"].astype(str),
        "acq_date": obs["date"].astype(str),
        "acq_time": "",
        "frp": obs["frp_mean"],
        "brightness": np.nan,
        "bright_t31": np.nan,
        "scan": np.nan,
        "track": np.nan,
        "confidence": "",
        "satellite": "N",
        "instrument": "VIIRS",
        "daynight": "",
        "type": np.nan,
        "baseline_or_population_reference": baseline_ref,
        "deviation_ratio": np.where(
            baseline_ref > 0,
            obs["frp_mean"] / baseline_ref.replace(0, np.nan),
            np.nan,
        ),
        "anomaly_score": obs.get("if_score", np.nan),
        "fire_event_detected": True,
        "severity": obs["severity"],
        "contributing_factors": obs["contributing_factors"].apply(_safe_list),
    })

    return out


if __name__ == "__main__":
    merge_and_export()
