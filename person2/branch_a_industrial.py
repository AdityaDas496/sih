"""
Person 2 — Branch A: Industrial Facility Anomaly Detection Pipeline.

Evaluates VIIRS hotspot detections in the context of known industrial
facilities. This branch does NOT decide whether the fire is "industrial" —
it only determines whether there is an anomalous thermal event near a
known facility. The final fire-type classification is Person 1's job.

Input:
    - data/viirs_clean.parquet                (cleaned VIIRS hotspots)
    - ../gujarat_golden_corridor_facilities.csv  (facility list)
    - OR ../gis/india_industrial_facilities_clean.csv
Output:
    - data/branch_a_results.parquet           (per-detection anomaly flags)
    - data/branch_b_input.parquet             (unmatched hotspots → Branch B)
"""

from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sklearn.ensemble import IsolationForest

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PERSON2_DIR.parent  # sih/
DATA_DIR = PERSON2_DIR / "data"
CLEAN_PARQUET = DATA_DIR / "viirs_clean.parquet"

# Facility CSV — try nationwide GIS layer first, fallback to regional
GIS_FACILITIES_CSV = PROJECT_DIR / "gis" / "india_industrial_facilities_clean.csv"
FACILITIES_CSV = PROJECT_DIR / "gujarat_golden_corridor_facilities.csv"

BRANCH_A_OUT = DATA_DIR / "branch_a_results.parquet"
BRANCH_B_INPUT = DATA_DIR / "branch_b_input.parquet"

# Configuration
BUFFER_METERS = 500         # spatial buffer around each facility
# EPSG:7755 is the India-wide Lambert Conformal Conic (NSIDC LCC) projection
# ensuring metric accuracy across all Indian states and territories
METRIC_CRS = "EPSG:7755"
MIN_HISTORY_DAYS = 60       # min observed days for per-facility model
CONTAMINATION = 0.05        # Isolation Forest contamination parameter
N_ESTIMATORS = 100
RANDOM_STATE = 42
ZSCORE_THRESHOLD = 3.0      # robust z-score threshold for baseline detector
PERCENTILE_THRESHOLD = 95   # hotspot count percentile threshold


# =====================================================================
# Step 5 — Spatial Join: hotspots → facilities
# =====================================================================

def spatial_join(hotspots: pd.DataFrame, facilities: pd.DataFrame):
    """
    Buffer each facility at BUFFER_METERS and assign hotspots.
    Returns (matched_df, unmatched_df).

    CRITICAL: The original hotspot coordinates (latitude, longitude) are
    preserved exactly as they came from VIIRS. We do NOT replace them
    with facility coordinates.
    """
    # Determine facility coordinate column names (supports lat/lon or latitude/longitude)
    fac_lat = "latitude" if "latitude" in facilities.columns else "lat"
    fac_lon = "longitude" if "longitude" in facilities.columns else "lon"

    # Only include non-colliding facility attributes in facility GeoDataFrame
    fac_cols = ["facility_id"]
    if "facility_name" in facilities.columns:
        fac_cols.append("facility_name")
    elif "name" in facilities.columns:
        facilities = facilities.rename(columns={"name": "facility_name"})
        fac_cols.append("facility_name")

    # Convert to GeoDataFrames
    hotspot_gdf = gpd.GeoDataFrame(
        hotspots,
        geometry=gpd.points_from_xy(hotspots["longitude"], hotspots["latitude"]),
        crs="EPSG:4326",
    )
    facility_gdf = gpd.GeoDataFrame(
        facilities[fac_cols],
        geometry=gpd.points_from_xy(facilities[fac_lon], facilities[fac_lat]),
        crs="EPSG:4326",
    )

    # Project to India-wide metric CRS for accurate buffering across all states
    hotspot_metric = hotspot_gdf.to_crs(METRIC_CRS)
    facility_metric = facility_gdf.to_crs(METRIC_CRS)

    # Buffer facilities
    facility_metric["geometry"] = facility_metric.geometry.buffer(BUFFER_METERS)

    # Spatial join (predicate: within)
    joined = gpd.sjoin(hotspot_metric, facility_metric, how="left", predicate="within")

    # Separate matched vs unmatched
    matched_mask = joined["index_right"].notna()

    # Log multi-matched detections
    dup_mask = joined.duplicated(subset=["detection_id"], keep=False)
    multi_matched = joined[dup_mask & matched_mask]
    if len(multi_matched) > 0:
        n_multi = multi_matched["detection_id"].nunique()
        print(f"  Multi-facility matches: {n_multi} detections -> keeping first match")
        joined = joined.drop_duplicates(subset=["detection_id"], keep="first")

    # Rebuild matched mask after dedup
    matched_mask = joined["index_right"].notna()

    matched = joined[matched_mask].copy()
    unmatched_ids = joined.loc[~matched_mask, "detection_id"].values

    # Get unmatched from original hotspot df (preserving original columns)
    unmatched = hotspots[hotspots["detection_id"].isin(unmatched_ids)].copy()

    print(f"  Matched to facility: {len(matched)}")
    print(f"  Unmatched (-> Branch B): {len(unmatched)}")

    # Keep only needed columns from the join
    # Preserve ALL original hotspot columns + facility_id, facility_name
    hotspot_cols = list(hotspots.columns)
    extra_cols = ["facility_id", "facility_name"]
    keep_cols = [c for c in hotspot_cols + extra_cols if c in matched.columns]
    matched = matched[keep_cols].copy()

    return matched, unmatched


# =====================================================================
# Step 6 — Build Facility-Day Table
# =====================================================================

def _haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters between two points."""
    R = 6_371_000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def build_facility_day_table(matched: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate matched hotspots into daily records per facility.

    IMPORTANT: We store per-detection info in a side table so we can
    later map facility-day anomaly flags back to original detections
    with their original coordinates.
    """
    matched = matched.copy()
    matched["date"] = pd.to_datetime(matched["date"])

    # Daily aggregation per facility
    agg = matched.groupby(["facility_id", "date"]).agg(
        hotspot_count=("frp", "size"),
        frp_total=("frp", "sum"),
        frp_max=("frp", "max"),
        frp_mean=("frp", "mean"),
        centroid_lat=("latitude", "mean"),
        centroid_lon=("longitude", "mean"),
        confidence_mean_val=("confidence_str", lambda x: (x == "high").mean()),
        lat_std=("latitude", "std"),
        lon_std=("longitude", "std"),
    ).reset_index()

    # Spatial spread: approximate as std of positions × 111km/degree → meters
    agg["spatial_spread_m"] = np.sqrt(
        agg["lat_std"].fillna(0) ** 2 + agg["lon_std"].fillna(0) ** 2
    ) * 111_000

    agg = agg.drop(columns=["lat_std", "lon_std"])
    agg = agg.rename(columns={"confidence_mean_val": "confidence_mean"})

    # Build full daily calendar for each facility
    facilities = agg["facility_id"].unique()
    date_min = agg["date"].min()
    date_max = agg["date"].max()
    full_dates = pd.date_range(date_min, date_max, freq="D")

    idx = pd.MultiIndex.from_product([facilities, full_dates], names=["facility_id", "date"])
    full_cal = pd.DataFrame(index=idx).reset_index()

    merged = full_cal.merge(agg, on=["facility_id", "date"], how="left")

    # Fill missing days with zeros
    fill_cols = ["hotspot_count", "frp_total", "frp_max", "frp_mean",
                 "spatial_spread_m", "confidence_mean"]
    for c in fill_cols:
        merged[c] = merged[c].fillna(0)

    # Days since last observation (vectorized)
    merged = merged.sort_values(["facility_id", "date"])
    merged["has_obs"] = merged["hotspot_count"] > 0

    last_obs = merged.groupby("facility_id")["date"].transform(
        lambda s: merged.loc[s.index, "date"].where(merged.loc[s.index, "has_obs"]).ffill().shift(1)
    )
    merged["days_since_last_obs"] = (merged["date"] - last_obs).dt.days

    print(f"  Facility-day table: {len(merged)} rows, {len(facilities)} facilities")
    return merged


# =====================================================================
# Step 7 — Feature Engineering (per facility-day, no lookahead)
# =====================================================================

def engineer_features(fac_day: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling statistics and anomaly features per facility."""
    df = fac_day.sort_values(["facility_id", "date"]).copy()

    feature_dfs = []
    for fac_id, grp in df.groupby("facility_id"):
        g = grp.copy()

        # Rolling 30-day statistics (min_periods=7 to avoid unstable early estimates)
        g["frp_rolling_mean_30d"] = (
            g["frp_mean"].rolling(30, min_periods=7).mean()
        )
        g["frp_rolling_median_30d"] = (
            g["frp_mean"].rolling(30, min_periods=7).median()
        )
        g["frp_rolling_std_30d"] = (
            g["frp_mean"].rolling(30, min_periods=7).std()
        )

        # Rolling MAD (Median Absolute Deviation)
        def _rolling_mad(series, window=30, min_periods=7):
            result = pd.Series(np.nan, index=series.index)
            for i in range(len(series)):
                start = max(0, i - window + 1)
                window_data = series.iloc[start:i + 1]
                if len(window_data.dropna()) >= min_periods:
                    med = window_data.median()
                    result.iloc[i] = (window_data - med).abs().median()
            return result

        g["frp_rolling_mad_30d"] = _rolling_mad(g["frp_mean"])

        # Robust Z-score: (current - rolling_median) / (1.4826 * MAD)
        # 1.4826 scales MAD to be consistent with std for normal distributions
        scaled_mad = g["frp_rolling_mad_30d"] * 1.4826
        scaled_mad = scaled_mad.replace(0, np.nan)  # avoid division by zero
        g["frp_zscore_robust"] = (
            (g["frp_mean"] - g["frp_rolling_median_30d"]) / scaled_mad
        )

        # Detection frequency over last 30 days
        g["detection_frequency_30d"] = (
            g["has_obs"].astype(int).rolling(30, min_periods=1).sum()
        )

        # Centroid displacement from rolling centroid
        g["centroid_lat_rolling"] = g["centroid_lat"].replace(0, np.nan).rolling(
            30, min_periods=7
        ).mean()
        g["centroid_lon_rolling"] = g["centroid_lon"].replace(0, np.nan).rolling(
            30, min_periods=7
        ).mean()
        g["centroid_displacement_m"] = _haversine_m(
            g["centroid_lat"].values, g["centroid_lon"].values,
            g["centroid_lat_rolling"].fillna(g["centroid_lat"]).values,
            g["centroid_lon_rolling"].fillna(g["centroid_lon"]).values,
        )
        # Zero displacement for no-observation days
        g.loc[~g["has_obs"], "centroid_displacement_m"] = 0

        # FRP change rate (day-over-day)
        g["frp_change_rate"] = g["frp_mean"].diff()

        feature_dfs.append(g)

    result = pd.concat(feature_dfs, ignore_index=True)
    print(f"  Features engineered: {result.shape[1]} columns")
    return result


# =====================================================================
# Step 8 — Minimum-History Filter
# =====================================================================

def split_by_history(fac_features: pd.DataFrame):
    """Split facilities into sufficient-history and low-history groups."""
    obs_counts = (
        fac_features[fac_features["has_obs"]]
        .groupby("facility_id")["date"]
        .nunique()
    )
    sufficient = obs_counts[obs_counts >= MIN_HISTORY_DAYS].index.tolist()
    low_hist = obs_counts[obs_counts < MIN_HISTORY_DAYS].index.tolist()

    # Include facilities with zero observations in low_hist
    all_facs = fac_features["facility_id"].unique()
    zero_obs = [f for f in all_facs if f not in obs_counts.index]
    low_hist.extend(zero_obs)

    print(f"  Sufficient history (>={MIN_HISTORY_DAYS} days): {len(sufficient)} facilities")
    print(f"  Low history (<{MIN_HISTORY_DAYS} days): {len(low_hist)} facilities")

    return sufficient, low_hist


# =====================================================================
# Step 9 — Statistical Baseline Detector (robust z-score + percentile)
# =====================================================================

def baseline_detector(fac_features: pd.DataFrame) -> pd.DataFrame:
    """
    Flag anomalies using robust z-score and hotspot count percentile.
    This is the critical fallback — works independently of ML models.
    """
    df = fac_features.copy()

    # Z-score flag
    df["zscore_flag"] = df["frp_zscore_robust"].abs() > ZSCORE_THRESHOLD

    # Per-facility hotspot count percentile flag
    def _percentile_flag(grp):
        threshold = grp["hotspot_count"].quantile(PERCENTILE_THRESHOLD / 100)
        return grp["hotspot_count"] > threshold

    df["count_percentile_flag"] = (
        df.groupby("facility_id", group_keys=False).apply(_percentile_flag)
    )

    # Combined baseline flag: either condition triggers
    df["baseline_anomaly"] = df["zscore_flag"] | df["count_percentile_flag"]

    flagged = df["baseline_anomaly"].sum()
    total_obs = df["has_obs"].sum()
    print(f"  Baseline detector: {flagged} anomalies flagged "
          f"({flagged/max(total_obs,1)*100:.1f}% of observed days)")

    return df


# =====================================================================
# Step 10 — Isolation Forest (per-facility + pooled)
# =====================================================================

FEATURE_COLS = [
    "frp_mean", "frp_max", "hotspot_count",
    "frp_zscore_robust", "detection_frequency_30d",
    "centroid_displacement_m", "spatial_spread_m",
    "frp_change_rate",
]


def _prepare_features(df: pd.DataFrame) -> np.ndarray:
    """Extract and impute feature matrix for Isolation Forest."""
    X = df[FEATURE_COLS].copy()
    X = X.fillna(0)  # fill NaN with 0 (early days with insufficient rolling window)
    return X.values


def train_isolation_forests(fac_features: pd.DataFrame, sufficient: list, low_hist: list):
    """
    Train per-facility IF for sufficient-history facilities,
    pooled IF for low-history facilities.
    Returns DataFrame with IF anomaly scores.
    """
    df = fac_features.copy()
    df["if_score"] = np.nan
    df["if_anomaly"] = False

    # Only train/predict on days with observations
    obs_mask = df["has_obs"]

    # --- Per-facility models ---
    for fac_id in sufficient:
        fac_mask = (df["facility_id"] == fac_id) & obs_mask
        fac_data = df.loc[fac_mask]

        if len(fac_data) < 10:
            continue

        X = _prepare_features(fac_data)
        model = IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
        )
        model.fit(X)

        scores = model.decision_function(X)
        preds = model.predict(X)

        df.loc[fac_mask, "if_score"] = scores
        df.loc[fac_mask, "if_anomaly"] = preds == -1

    # --- Pooled model for low-history facilities ---
    if low_hist:
        pool_mask = df["facility_id"].isin(low_hist) & obs_mask
        pool_data = df.loc[pool_mask]

        if len(pool_data) >= 10:
            X_pool = _prepare_features(pool_data)
            pooled_model = IsolationForest(
                n_estimators=N_ESTIMATORS,
                contamination=CONTAMINATION,
                random_state=RANDOM_STATE,
            )
            pooled_model.fit(X_pool)

            scores_pool = pooled_model.decision_function(X_pool)
            preds_pool = pooled_model.predict(X_pool)

            df.loc[pool_mask, "if_score"] = scores_pool
            df.loc[pool_mask, "if_anomaly"] = preds_pool == -1

    if_flagged = df["if_anomaly"].sum()
    print(f"  Isolation Forest: {if_flagged} anomalies flagged")

    return df


# =====================================================================
# Step 11 — Combine into Branch A output
# =====================================================================

def combine_branch_a(fac_features: pd.DataFrame) -> pd.DataFrame:
    """
    Merge z-score baseline + Isolation Forest into severity buckets.
    Agreement → HIGH, one flags → MEDIUM, neither → LOW.
    """
    df = fac_features.copy()

    def _severity(row):
        if not row["has_obs"]:
            return "NONE"
        baseline = row.get("baseline_anomaly", False)
        iso = row.get("if_anomaly", False)
        if baseline and iso:
            return "HIGH"
        elif baseline or iso:
            return "MEDIUM"
        else:
            return "LOW"

    df["severity"] = df.apply(_severity, axis=1)
    df["fire_event_detected"] = df["severity"].isin(["HIGH", "MEDIUM"])

    # Contributing factors
    def _factors(row):
        factors = []
        if row.get("zscore_flag", False):
            factors.append("frp_spike")
        if row.get("count_percentile_flag", False):
            factors.append("hotspot_count_increase")
        if row.get("if_anomaly", False):
            factors.append("isolation_forest_outlier")
        if row.get("centroid_displacement_m", 0) > 500:
            factors.append("centroid_shift")
        if row.get("spatial_spread_m", 0) > 200:
            factors.append("spatial_spread")
        return factors

    df["contributing_factors"] = df.apply(_factors, axis=1)

    # Summary
    sev_counts = df[df["has_obs"]]["severity"].value_counts()
    print(f"  Branch A severity distribution:\n{sev_counts.to_string()}")

    return df


# =====================================================================
# Main pipeline
# =====================================================================

def _resolve_facilities_csv() -> Path:
    """Find the facility CSV — try nationwide GIS layer first, then regional."""
    if GIS_FACILITIES_CSV.exists():
        return GIS_FACILITIES_CSV
    if FACILITIES_CSV.exists():
        return FACILITIES_CSV
    raise FileNotFoundError(
        f"No facility CSV found at {GIS_FACILITIES_CSV} or {FACILITIES_CSV}. "
        "Run the facility generation step first."
    )


def run_branch_a():
    """Execute the full Branch A pipeline."""
    print("\n" + "=" * 60)
    print("BRANCH A -- Industrial Facility Anomaly Detection")
    print("=" * 60)

    # Load data
    print("\nLoading cleaned VIIRS data...")
    hotspots = pd.read_parquet(CLEAN_PARQUET)

    print("Loading facility data...")
    fac_csv = _resolve_facilities_csv()
    facilities = pd.read_csv(fac_csv)
    print(f"  Facilities loaded: {len(facilities)} (from {fac_csv.name})")

    # Step 5 — Spatial join
    print("\nStep 5: Spatial join (hotspots -> facilities)...")
    matched, unmatched = spatial_join(hotspots, facilities)

    # Save unmatched for Branch B
    unmatched.to_parquet(BRANCH_B_INPUT, index=False)
    print(f"  Branch B input saved: {BRANCH_B_INPUT}")

    if len(matched) == 0:
        print("WARNING: No hotspots matched any facility. Branch A will be empty.")
        empty = pd.DataFrame()
        empty.to_parquet(BRANCH_A_OUT, index=False)
        return empty, unmatched, hotspots

    # Step 6 — Facility-day table
    print("\nStep 6: Building facility-day table...")
    fac_day = build_facility_day_table(matched)

    # Step 7 — Feature engineering
    print("\nStep 7: Feature engineering...")
    fac_features = engineer_features(fac_day)

    # Step 8 — History filter
    print("\nStep 8: Minimum-history filter...")
    sufficient, low_hist = split_by_history(fac_features)

    # Step 9 — Statistical baseline
    print("\nStep 9: Statistical baseline detector...")
    fac_features = baseline_detector(fac_features)

    # Step 10 — Isolation Forest
    print("\nStep 10: Isolation Forest training...")
    fac_features = train_isolation_forests(fac_features, sufficient, low_hist)

    # Step 11 — Combine
    print("\nStep 11: Combining detectors into severity buckets...")
    result = combine_branch_a(fac_features)

    # Save
    result.to_parquet(BRANCH_A_OUT, index=False)
    print(f"\nBranch A output saved: {BRANCH_A_OUT}")

    return result, unmatched, matched


if __name__ == "__main__":
    result, unmatched, matched = run_branch_a()
    print("\nBranch A complete.")
