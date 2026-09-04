"""
Person 2 — Evaluation: Synthetic anomaly injection + Branch B sanity check.

Step 16: Inject artificial FRP spikes into real facility time series,
         run detector, compute precision/recall/F1/PR-AUC.
Step 17: Spot-check top-N Branch B detections for manual review.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    precision_recall_curve, auc,
)

from branch_a_industrial import (
    engineer_features,
    baseline_detector,
    train_isolation_forests,
    combine_branch_a,
    split_by_history,
    FEATURE_COLS,
)

# Resolve paths relative to this script's directory
PERSON2_DIR = Path(__file__).resolve().parent
DATA_DIR = PERSON2_DIR / "data"


# =====================================================================
# Step 16 — Synthetic Anomaly Injection Test (Branch A)
# =====================================================================

def inject_anomalies(
    fac_day: pd.DataFrame,
    n_injections: int = 20,
    spike_multiplier_range: tuple = (3.0, 10.0),
    seed: int = 123,
) -> tuple:
    """
    Inject artificial FRP spikes into real facility time series.
    Returns (modified_df, injection_labels).
    """
    rng = np.random.default_rng(seed)
    df = fac_day.copy()

    # Get facilities with observations
    obs_facs = df[df["has_obs"]]["facility_id"].unique()
    if len(obs_facs) == 0:
        print("WARNING: No observed facilities to inject anomalies into.")
        return df, pd.Series(False, index=df.index)

    # Mark all original rows as non-injected
    df["injected_anomaly"] = False

    # Select random facility-days for injection
    obs_rows = df[df["has_obs"]].index.tolist()
    n_injections = min(n_injections, len(obs_rows))
    inject_indices = rng.choice(obs_rows, size=n_injections, replace=False)

    for idx in inject_indices:
        fac_id = df.loc[idx, "facility_id"]
        fac_mask = (df["facility_id"] == fac_id) & df["has_obs"]
        fac_median_frp = df.loc[fac_mask, "frp_mean"].median()

        if fac_median_frp == 0 or np.isnan(fac_median_frp):
            fac_median_frp = 10.0  # fallback

        multiplier = rng.uniform(*spike_multiplier_range)
        spike_frp = fac_median_frp * multiplier

        # Inject the spike
        df.loc[idx, "frp_mean"] = spike_frp
        df.loc[idx, "frp_max"] = spike_frp * 1.2
        df.loc[idx, "frp_total"] = spike_frp * rng.integers(3, 8)
        df.loc[idx, "hotspot_count"] = df.loc[idx, "hotspot_count"] + rng.integers(3, 10)
        df.loc[idx, "injected_anomaly"] = True

    print(f"  Injected {n_injections} synthetic anomalies across "
          f"{len(set(df.loc[inject_indices, 'facility_id']))} facilities")

    return df, df["injected_anomaly"]


def evaluate_branch_a(fac_day_original: pd.DataFrame) -> dict:
    """
    Full evaluation pipeline:
    1. Inject anomalies into real data
    2. Re-run feature engineering + detectors
    3. Compute precision, recall, F1, PR-AUC
    """
    print("\n--- Synthetic Anomaly Injection Evaluation ---")

    # 1. Inject
    print("\nInjecting synthetic anomalies...")
    fac_day_injected, ground_truth = inject_anomalies(fac_day_original)

    if ground_truth.sum() == 0:
        print("No anomalies could be injected. Skipping evaluation.")
        return {}

    # 2. Re-run feature engineering
    print("Re-running feature engineering on injected data...")
    fac_features = engineer_features(fac_day_injected)

    # 3. Re-run detectors
    print("Re-running baseline detector...")
    fac_features = baseline_detector(fac_features)

    print("Re-running Isolation Forest...")
    sufficient, low_hist = split_by_history(fac_features)
    fac_features = train_isolation_forests(fac_features, sufficient, low_hist)

    # 4. Combine
    result = combine_branch_a(fac_features)

    # 5. Evaluate — only on observed days
    obs_mask = result["has_obs"]
    y_true = result.loc[obs_mask, "injected_anomaly"].astype(int).values
    y_pred = result.loc[obs_mask, "fire_event_detected"].astype(int).values

    # For PR-AUC, use the IF score as continuous prediction
    y_scores = result.loc[obs_mask, "if_score"].fillna(0).values
    # Invert scores: more negative = more anomalous → higher anomaly probability
    y_scores_inv = -y_scores

    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # PR curve and AUC
    precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_scores_inv)
    pr_auc = auc(recall_curve, precision_curve)

    # Detection delay: for each injected anomaly, count how many days
    # until the detector first flags it (within a ±2 day window)
    injected_days = result[result["injected_anomaly"]]
    detected_days = result[result["fire_event_detected"]]
    delays = []
    for _, inj_row in injected_days.iterrows():
        fac_detections = detected_days[detected_days["facility_id"] == inj_row["facility_id"]]
        if len(fac_detections) == 0:
            delays.append(np.nan)  # missed
            continue
        day_diffs = (fac_detections["date"] - inj_row["date"]).dt.days.abs()
        min_delay = day_diffs.min()
        delays.append(min_delay)

    avg_delay = np.nanmean(delays) if delays else np.nan

    metrics = {
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "pr_auc": pr_auc,
        "avg_detection_delay_days": avg_delay,
        "n_injected": int(ground_truth.sum()),
        "n_detected": int(y_pred[y_true == 1].sum()),
        "n_false_positives": int(y_pred[y_true == 0].sum()),
    }

    print("\n+-----------------------------------------+")
    print("|    Branch A Evaluation Results          |")
    print("+-----------------------------------------+")
    print(f"|  Precision:           {prec:.4f}            |")
    print(f"|  Recall:              {rec:.4f}            |")
    print(f"|  F1 Score:            {f1:.4f}            |")
    print(f"|  PR-AUC:              {pr_auc:.4f}            |")
    print(f"|  Avg Detection Delay: {avg_delay:.1f} days       |")
    print(f"|  Injected:            {metrics['n_injected']}                |")
    print(f"|  Detected:            {metrics['n_detected']}                |")
    print(f"|  False Positives:     {metrics['n_false_positives']}              |")
    print("+-----------------------------------------+")

    return metrics


# =====================================================================
# Step 17 — Branch B Sanity Check
# =====================================================================

def sanity_check_branch_b(n_top: int = 20) -> pd.DataFrame:
    """
    Pull top-N flagged Branch B detections for manual map inspection.
    Print coordinates and attributes for spot-checking.
    """
    branch_b_out = DATA_DIR / "branch_b_results.parquet"
    if not branch_b_out.exists():
        print("Branch B results not found. Run branch_b_open_area.py first.")
        return pd.DataFrame()

    df = pd.read_parquet(branch_b_out)

    # Get top flagged detections (most anomalous by IF score)
    flagged = df[df["fire_event_detected"]].copy()
    if len(flagged) == 0:
        print("No Branch B detections flagged. Nothing to sanity-check.")
        return pd.DataFrame()

    flagged = flagged.sort_values("if_score", ascending=True)  # most negative = most anomalous
    top_n = flagged.head(n_top)

    print(f"\n--- Branch B Sanity Check: Top {min(n_top, len(top_n))} Flagged Detections ---")
    print(f"{'Rank':<5} {'Severity':<8} {'IF Score':<10} {'FRP':<8} "
          f"{'Lat':>9} {'Lon':>10} {'Date':<12} {'BT4':>6} {'BT5':>6}")
    print("-" * 80)
    for i, (_, row) in enumerate(top_n.iterrows(), 1):
        print(f"{i:<5} {row['severity']:<8} {row['if_score']:<10.4f} "
              f"{row['frp']:<8.1f} {row['latitude']:>9.4f} {row['longitude']:>10.4f} "
              f"{str(row['date'])[:10]:<12} {row['bright_ti4']:>6.1f} {row['bright_ti5']:>6.1f}")

    print(f"\n-> Manually verify these coordinates on a map to confirm "
          f"threshold calibration.")
    print(f"  Google Maps: https://www.google.com/maps/@"
          f"{top_n.iloc[0]['latitude']},{top_n.iloc[0]['longitude']},12z")

    return top_n


if __name__ == "__main__":
    # Step 16 — needs facility-day table from Branch A
    branch_a_out = DATA_DIR / "branch_a_results.parquet"
    if branch_a_out.exists():
        fac_day = pd.read_parquet(branch_a_out)
        if len(fac_day) > 0:
            metrics = evaluate_branch_a(fac_day)
    else:
        print("Branch A results not found. Run branch_a_industrial.py first.")

    # Step 17
    sanity_check_branch_b()
