"""
Person 2 — FIRMS VIIRS Data Pull.

Pull VIIRS hotspot data from NASA FIRMS API or generate synthetic data
for pipeline testing.

Usage:
    python firms_pull.py                  # uses FIRMS_MAP_KEY env var
    python firms_pull.py --synthetic      # generate synthetic data (no API needed)

Output: data/viirs_raw.csv

Environment Variable:
    FIRMS_MAP_KEY — Your NASA FIRMS API key.
    Register at: https://firms.modaps.eosdis.nasa.gov/api/area/
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from region_config import BBOX, COUNTRY_CODE, REGION_NAME, filter_points_within_india

# ---------------------------------------------------------------------------
# FIRMS API configuration
# ---------------------------------------------------------------------------
# NEVER hard-code the key. Use environment variable FIRMS_MAP_KEY.
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")

# Dedicated NASA FIRMS country endpoint for nationwide coverage
FIRMS_COUNTRY_URL = "https://firms.modaps.eosdis.nasa.gov/api/country/csv"
SOURCE = os.environ.get("FIRMS_SOURCE", "VIIRS_SNPP_NRT")   # VIIRS 375 m near-real-time
DAY_RANGE = int(os.environ.get("FIRMS_DAY_RANGE", "10"))   # max 10 for NRT endpoint on free tier

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PERSON2_DIR.parent
DATA_DIR = PERSON2_DIR / "data"
RAW_CSV = DATA_DIR / "viirs_raw.csv"
GIS_FACILITIES_CSV = PROJECT_DIR / "gis" / "india_industrial_facilities_clean.csv"


def pull_firms_data() -> pd.DataFrame:
    """Download VIIRS hotspot CSV from FIRMS for India and enforce strict boundary."""
    if not FIRMS_MAP_KEY:
        raise ValueError(
            "FIRMS_MAP_KEY environment variable is not set. "
            "Register at https://firms.modaps.eosdis.nasa.gov/api/area/ "
            "and set: export FIRMS_MAP_KEY=your_key_here"
        )
    url = f"{FIRMS_COUNTRY_URL}/{FIRMS_MAP_KEY}/{SOURCE}/{COUNTRY_CODE}/{DAY_RANGE}"
    print(f"Requesting FIRMS country data for {COUNTRY_CODE} ({SOURCE}, {DAY_RANGE} days):\n  {url}")

    resp = requests.get(url, timeout=180)
    resp.raise_for_status()

    # FIRMS returns CSV text directly
    from io import StringIO
    df = pd.read_csv(StringIO(resp.text))
    print(f"Rows received from FIRMS: {len(df)}")

    # Enforce strict spatial clipping to India borders
    print("Validating and filtering detections against India boundary...")
    df = filter_points_within_india(df)
    print(f"Final confirmed India detections: {len(df)}")
    return df


def generate_synthetic_data(n_days: int = 180, seed: int = 42) -> pd.DataFrame:
    """
    Generate realistic synthetic VIIRS-like hotspot data across India for pipeline testing.
    Mimics the column schema of real FIRMS VIIRS CSV output.
    Uses real nationwide facility locations and guarantees all detections stay strictly within India.
    """
    rng = np.random.default_rng(seed)

    # --- Load nationwide facility locations if available ---
    if GIS_FACILITIES_CSV.exists():
        fac_df = pd.read_csv(GIS_FACILITIES_CSV)
        lat_col = "latitude" if "latitude" in fac_df.columns else "lat"
        lon_col = "longitude" if "longitude" in fac_df.columns else "lon"
        # Sample facilities across different states in India
        sample_size = min(60, len(fac_df))
        sampled_facs = fac_df.sample(n=sample_size, random_state=seed).reset_index(drop=True)
        facility_lats = sampled_facs[lat_col].values
        facility_lons = sampled_facs[lon_col].values
        n_facilities = len(sampled_facs)
    else:
        n_facilities = 30
        facility_lats = rng.uniform(BBOX["south"] + 2.0, BBOX["north"] - 2.0, n_facilities)
        facility_lons = rng.uniform(BBOX["west"] + 2.0, BBOX["east"] - 2.0, n_facilities)

    n_open_area = 250
    records = []

    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n_days, freq="D")
    dates_list = dates.tolist()

    # --- Industrial hotspots (clustered near nationwide facilities) ---
    for fac_idx in range(n_facilities):
        base_freq = rng.uniform(0.3, 0.9)
        base_frp = rng.uniform(15, 90)
        frp_std = base_frp * 0.25

        for day in dates_list:
            if rng.random() > base_freq:
                continue

            n_det = rng.integers(1, 4)
            for _ in range(n_det):
                frp = max(0.5, rng.normal(base_frp, frp_std))
                lat = facility_lats[fac_idx] + rng.normal(0, 0.002)
                lon = facility_lons[fac_idx] + rng.normal(0, 0.002)
                bright_ti4 = rng.uniform(310, 360)
                bright_ti5 = rng.uniform(280, 310)
                scan = round(rng.uniform(0.39, 1.2), 2)
                track = round(rng.uniform(0.39, 1.0), 2)
                conf = rng.choice(["low", "nominal", "high"], p=[0.1, 0.5, 0.4])
                dn = rng.choice(["D", "N"], p=[0.6, 0.4])

                records.append({
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "bright_ti4": round(bright_ti4, 1),
                    "bright_ti5": round(bright_ti5, 1),
                    "scan": scan,
                    "track": track,
                    "acq_date": day.strftime("%Y-%m-%d"),
                    "acq_time": f"{rng.integers(0,24):02d}{rng.integers(0,60):02d}",
                    "satellite": "N",
                    "instrument": "VIIRS",
                    "confidence": conf,
                    "version": "2.0NRT",
                    "frp": round(frp, 1),
                    "daynight": dn,
                    "type": 0,
                })

    # --- Inject a few anomalous spikes (known fire events) ---
    spike_days = rng.choice(len(dates_list), size=8, replace=False)
    spike_facs = rng.choice(n_facilities, size=8, replace=False)
    for sd, sf in zip(spike_days, spike_facs):
        spike_frp = rng.uniform(250, 600)
        for _ in range(rng.integers(5, 12)):
            records.append({
                "latitude": round(facility_lats[sf] + rng.normal(0, 0.003), 5),
                "longitude": round(facility_lons[sf] + rng.normal(0, 0.003), 5),
                "bright_ti4": round(rng.uniform(370, 500), 1),
                "bright_ti5": round(rng.uniform(310, 370), 1),
                "scan": round(rng.uniform(0.5, 1.5), 2),
                "track": round(rng.uniform(0.5, 1.3), 2),
                "acq_date": dates_list[sd].strftime("%Y-%m-%d"),
                "acq_time": f"{rng.integers(0,24):02d}{rng.integers(0,60):02d}",
                "satellite": "N",
                "instrument": "VIIRS",
                "confidence": "high",
                "version": "2.0NRT",
                "frp": round(spike_frp, 1),
                "daynight": rng.choice(["D", "N"]),
                "type": 0,
            })

    # --- Open-area hotspots across India ---
    for _ in range(n_open_area * 3):  # over-sample then filter to India
        day = rng.choice(dates_list)
        records.append({
            "latitude": round(rng.uniform(BBOX["south"] + 1.0, BBOX["north"] - 1.0), 5),
            "longitude": round(rng.uniform(BBOX["west"] + 1.0, BBOX["east"] - 1.0), 5),
            "bright_ti4": round(rng.uniform(305, 400), 1),
            "bright_ti5": round(rng.uniform(275, 320), 1),
            "scan": round(rng.uniform(0.39, 1.5), 2),
            "track": round(rng.uniform(0.39, 1.3), 2),
            "acq_date": day.strftime("%Y-%m-%d"),
            "acq_time": f"{rng.integers(0,24):02d}{rng.integers(0,60):02d}",
            "satellite": "N",
            "instrument": "VIIRS",
            "confidence": rng.choice(["low", "nominal", "high"], p=[0.15, 0.50, 0.35]),
            "version": "2.0NRT",
            "frp": round(max(0.5, rng.exponential(30)), 1),
            "daynight": rng.choice(["D", "N"]),
            "type": 0,
        })

    df = pd.DataFrame(records)
    # Strictly filter points to only those within India
    df = filter_points_within_india(df)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    print(f"Synthetic VIIRS records generated within India: {len(df)}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull VIIRS hotspot data from FIRMS")
    parser.add_argument("--synthetic", action="store_true",
                        help="Generate synthetic data instead of calling FIRMS API")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.synthetic or not FIRMS_MAP_KEY:
        if not args.synthetic:
            print("WARNING: FIRMS_MAP_KEY not set. Falling back to synthetic data generation.")
            print("         Set environment variable FIRMS_MAP_KEY or register at:")
            print("         https://firms.modaps.eosdis.nasa.gov/api/area/")
        df = generate_synthetic_data()
    else:
        df = pull_firms_data()

    df.to_csv(RAW_CSV, index=False)
    print(f"Saved: {RAW_CSV}")
    print(f"Date range: {df['acq_date'].min()} -> {df['acq_date'].max()}")
    print(f"Columns: {list(df.columns)}")
