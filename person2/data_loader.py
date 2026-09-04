"""
Person 2 — Data Loader & Cleaner.

Load raw VIIRS hotspot CSV, standardize column names, parse timestamps,
flag low-confidence detections, and assign stable deterministic detection IDs.

Input:  data/viirs_raw.csv
Output: data/viirs_clean.parquet

CRITICAL: This module preserves ALL original FIRMS/VIIRS columns through the
pipeline so they are available for the downstream Person 1 handoff.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from region_config import filter_points_within_india

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
DATA_DIR = PERSON2_DIR / "data"
RAW_CSV = DATA_DIR / "viirs_raw.csv"
CLEAN_PARQUET = DATA_DIR / "viirs_clean.parquet"

# Columns we require (VIIRS SNPP schema)
REQUIRED_COLS = [
    "latitude", "longitude", "acq_date", "acq_time",
    "frp", "confidence", "bright_ti4", "bright_ti5",
    "scan", "track", "daynight",
]


def _make_deterministic_id(row: pd.Series) -> str:
    """
    Construct a stable, unique detection_id from source fields.

    The same detection will always receive the same ID regardless of
    pipeline re-runs, as long as the source fields are unchanged.
    """
    key_str = (
        f"{row['acq_date']}_{row['acq_time_str']}_"
        f"{row['latitude']:.5f}_{row['longitude']:.5f}_"
        f"{row.get('satellite', 'N')}_{row['frp']}"
    )
    hash_hex = hashlib.sha256(key_str.encode()).hexdigest()[:12]
    return f"DET-{hash_hex}"


def load_and_clean(path: Path = RAW_CSV) -> pd.DataFrame:
    """Load raw VIIRS CSV, standardize, and flag low-confidence rows.

    Preserves all original FIRMS columns so downstream modules can
    access acq_date, acq_time, satellite, instrument, type, etc.
    """
    df = pd.read_csv(path)
    print(f"Raw rows loaded: {len(df)}")

    # ------------------------------------------------------------------
    # 1. Standardize column names (FIRMS may use varying case)
    # ------------------------------------------------------------------
    df.columns = df.columns.str.strip().str.lower()

    # Check for required columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # ------------------------------------------------------------------
    # 2. Parse timestamp
    # ------------------------------------------------------------------
    # acq_time is HHMM as int; pad to 4 digits then combine with date
    df["acq_time_str"] = df["acq_time"].astype(str).str.zfill(4)
    df["datetime"] = pd.to_datetime(
        df["acq_date"].astype(str) + " " + df["acq_time_str"],
        format="%Y-%m-%d %H%M",
        errors="coerce",
    )
    df["date"] = pd.to_datetime(df["acq_date"])

    # ------------------------------------------------------------------
    # 3. Type coercion & bounds sanity
    # ------------------------------------------------------------------
    for col in ["latitude", "longitude", "frp", "bright_ti4", "bright_ti5", "scan", "track"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with null coordinates or FRP (unusable)
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude", "frp"]).copy()
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} rows with null lat/lon/frp")

    # Enforce strict spatial containment within India
    df = filter_points_within_india(df)

    # ------------------------------------------------------------------
    # 4. Flag low-confidence detections (keep, don't delete)
    # ------------------------------------------------------------------
    # VIIRS confidence is categorical: "low", "nominal", "high"
    # or numeric 0-100 depending on product version
    if pd.api.types.is_string_dtype(df["confidence"]) or df["confidence"].dtype == object:
        df["confidence_str"] = df["confidence"].str.strip().str.lower()
        df["low_conf"] = df["confidence_str"] == "low"
    else:
        df["confidence_str"] = pd.cut(
            df["confidence"],
            bins=[-1, 33, 66, 100],
            labels=["low", "nominal", "high"],
        ).astype(str)
        df["low_conf"] = df["confidence"] < 33

    low_count = df["low_conf"].sum()
    print(f"Low-confidence detections flagged: {low_count} ({low_count/len(df)*100:.1f}%)")

    # ------------------------------------------------------------------
    # 5. Encode daynight as binary
    # ------------------------------------------------------------------
    df["is_night"] = df["daynight"].str.strip().str.upper() == "N"

    # ------------------------------------------------------------------
    # 6. Derived feature: FRP per pixel area
    # ------------------------------------------------------------------
    pixel_area = df["scan"] * df["track"]  # approximate footprint in km²
    df["frp_per_area"] = np.where(pixel_area > 0, df["frp"] / pixel_area, np.nan)

    # ------------------------------------------------------------------
    # 7. Assign a stable, deterministic detection ID
    # ------------------------------------------------------------------
    df = df.reset_index(drop=True)
    df["detection_id"] = df.apply(_make_deterministic_id, axis=1)

    # Handle the (extremely unlikely) case of hash collisions
    dup_mask = df.duplicated(subset=["detection_id"], keep=False)
    if dup_mask.any():
        collision_count = 0
        for idx in df[dup_mask].index:
            collision_count += 1
            df.at[idx, "detection_id"] = f"{df.at[idx, 'detection_id']}-{collision_count}"

    # ------------------------------------------------------------------
    # 8. Preserve original FIRMS columns + add derived columns
    # ------------------------------------------------------------------
    # We keep ALL columns. The output includes:
    # - Original: latitude, longitude, acq_date, acq_time, frp, bright_ti4,
    #   bright_ti5, scan, track, confidence, daynight, satellite, instrument,
    #   version, type
    # - Derived: detection_id, date, datetime, acq_time_str, confidence_str,
    #   low_conf, is_night, frp_per_area
    #
    # This is critical: downstream modules need the original FIRMS columns
    # for the Person 1 handoff.

    print(f"Clean rows: {len(df)}")
    print(f"Date range: {df['date'].min().date()} -> {df['date'].max().date()}")
    return df


if __name__ == "__main__":
    df = load_and_clean()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CLEAN_PARQUET, index=False)
    print(f"Saved: {CLEAN_PARQUET}")
    print(df.head())
