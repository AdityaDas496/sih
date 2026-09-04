"""
Person 2 — Branch B: Open-Area Fallback Anomaly Detection.

Evaluates VIIRS hotspot detections that did NOT match any known industrial
facility. Uses population-level anomaly detection across all open-area
detections in the region.

This branch does NOT decide whether the fire is "natural" — it only
determines whether there is an anomalous thermal event in open areas.
The final fire-type classification is Person 1's job.

Input:  data/branch_b_input.parquet  (unmatched hotspots from Branch A)
Output: data/branch_b_results.parquet
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
DATA_DIR = PERSON2_DIR / "data"
BRANCH_B_INPUT = DATA_DIR / "branch_b_input.parquet"
BRANCH_B_OUT = DATA_DIR / "branch_b_results.parquet"

# Configuration
CONTAMINATION = 0.05
N_ESTIMATORS = 100
RANDOM_STATE = 42


# =====================================================================
# Step 13 — Feature set for Branch B
# =====================================================================

BRANCH_B_FEATURES = [
    "frp", "bright_ti4", "bright_ti5", "scan", "track",
    "is_night", "frp_per_area",
]


def prepare_branch_b_features(df: pd.DataFrame) -> tuple:
    """Extract per-detection FIRMS attributes for Branch B model."""
    features = df.copy()

    # Encode confidence as numeric
    conf_map = {"low": 0, "nominal": 1, "high": 2}
    features["confidence_num"] = features["confidence_str"].map(conf_map).fillna(1)

    # Ensure is_night is numeric
    features["is_night"] = features["is_night"].astype(int)

    # Feature columns (including confidence_num)
    feat_cols = BRANCH_B_FEATURES + ["confidence_num"]

    X = features[feat_cols].fillna(0).values
    return X, feat_cols


# =====================================================================
# Step 14 — Regional Isolation Forest on Branch B attributes
# =====================================================================

def train_branch_b_model(df: pd.DataFrame):
    """
    Train one Isolation Forest on the entire open-area population.
    Flags detections that are attribute-wise unusual relative to the
    regional population — NOT relative to a location's own history.
    """
    X, feat_cols = prepare_branch_b_features(df)

    model = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    model.fit(X)

    scores = model.decision_function(X)
    preds = model.predict(X)

    df = df.copy()
    df["if_score"] = scores
    df["if_anomaly"] = preds == -1

    print(f"  Branch B Isolation Forest trained on {len(X)} detections")
    print(f"  Anomalies flagged: {(preds == -1).sum()}")

    return df, model


# =====================================================================
# Step 15 — Severity buckets for Branch B
# =====================================================================

def assign_severity_branch_b(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign severity based on Isolation Forest anomaly score.
    Since Branch B has no baseline z-score, use score percentiles:
      - if_score in bottom 2% of all scores → HIGH
      - if_score in bottom 5% (but above 2%) → MEDIUM
      - else → LOW
    """
    df = df.copy()

    # Isolation Forest: more negative score = more anomalous
    score_2pct = df["if_score"].quantile(0.02)
    score_5pct = df["if_score"].quantile(0.05)

    def _severity(score, is_anomaly):
        if is_anomaly and score <= score_2pct:
            return "HIGH"
        elif is_anomaly:
            return "MEDIUM"
        else:
            return "LOW"

    df["severity"] = [
        _severity(s, a)
        for s, a in zip(df["if_score"], df["if_anomaly"])
    ]
    df["fire_event_detected"] = df["severity"].isin(["HIGH", "MEDIUM"])

    # Contributing factors for Branch B
    frp_95 = df["frp"].quantile(0.95)
    bt4_95 = df["bright_ti4"].quantile(0.95)
    fpa_95 = df["frp_per_area"].quantile(0.95)

    def _factors(row):
        factors = []
        if row["if_anomaly"]:
            factors.append("isolation_forest_outlier")
        if row["frp"] > frp_95:
            factors.append("frp_spike")
        if row["bright_ti4"] > bt4_95:
            factors.append("high_brightness_ti4")
        if row.get("frp_per_area", 0) > fpa_95:
            factors.append("high_frp_density")
        return factors

    df["contributing_factors"] = df.apply(_factors, axis=1)

    sev_counts = df["severity"].value_counts()
    print(f"  Branch B severity distribution:\n{sev_counts.to_string()}")

    return df


# =====================================================================
# Main pipeline
# =====================================================================

def run_branch_b():
    """Execute the full Branch B pipeline."""
    print("\n" + "=" * 60)
    print("BRANCH B -- Open-Area Fallback Detection")
    print("=" * 60)

    # Step 12 — Load unmatched hotspots
    print("\nStep 12: Loading unmatched hotspot dataset...")
    if not BRANCH_B_INPUT.exists():
        raise FileNotFoundError(
            f"{BRANCH_B_INPUT} not found. Run branch_a_industrial.py first."
        )
    df = pd.read_parquet(BRANCH_B_INPUT)
    print(f"  Unmatched detections loaded: {len(df)}")

    if len(df) == 0:
        print("WARNING: No unmatched hotspots. Branch B will be empty.")
        empty = pd.DataFrame()
        empty.to_parquet(BRANCH_B_OUT, index=False)
        return empty

    # Step 13–14 — Feature extraction + Isolation Forest
    print("\nSteps 13-14: Training regional Isolation Forest...")
    df, model = train_branch_b_model(df)

    # Step 15 — Severity assignment
    print("\nStep 15: Assigning severity buckets...")
    result = assign_severity_branch_b(df)

    # Save
    result.to_parquet(BRANCH_B_OUT, index=False)
    print(f"\nBranch B output saved: {BRANCH_B_OUT}")

    return result


if __name__ == "__main__":
    result = run_branch_b()
    print("\nBranch B complete.")
