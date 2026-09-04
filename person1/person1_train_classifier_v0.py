import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import GroupShuffleSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, balanced_accuracy_score, f1_score

INPUT = "person1_fire_type_classification_worldcover.csv"

MODEL_OUT = "person1_fire_type_classifier_v0.joblib"
PRED_OUT = "person1_fire_type_classification_predictions_v0.csv"
METRICS_OUT = "person1_classifier_v0_metrics.csv"
CM_OUT = "person1_classifier_v0_confusion_matrix.csv"

LABELS = ["industrial_proxy", "forest_proxy", "other_natural_proxy"]


def add_features(df):
    df = df.copy()

    dt = pd.to_datetime(df["acq_date"].astype(str) + " " + df["acq_time"].astype(str).str.zfill(4), format="%Y-%m-%d %H%M", errors="coerce")

    df["hour"] = dt.dt.hour + dt.dt.minute / 60.0
    df["month"] = dt.dt.month
    df["dayofyear"] = dt.dt.dayofyear

    df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
    df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)

    df["is_day"] = ((df["hour"] >= 6) & (df["hour"] < 18)).astype(int)

    df["spatial_group"] = (
        np.floor(df["latitude"].astype(float) * 2).astype(int).astype(str)
        + "_"
        + np.floor(df["longitude"].astype(float) * 2).astype(int).astype(str)
    )

    return df


def make_X(df, medians=None):
    numeric_features = [
        "frp",
        "brightness",
        "bright_t31",
        "scan",
        "track",
        "distance_to_nearest_industry_km",
        "worldcover_class",
        "forest_like_landcover",
        "open_vegetation_landcover",
        "builtup_landcover",
        "bare_sparse_landcover",
        "water_wetland_landcover",
        "moss_lichen_landcover",
        "hour",
        "month",
        "dayofyear",
        "sin_hour",
        "cos_hour",
        "sin_month",
        "cos_month",
        "is_day"
    ]

    categorical_features = ["nearest_facility_type"]

    for column in numeric_features:
        if column not in df.columns:
            df[column] = np.nan

    for column in categorical_features:
        if column not in df.columns:
            df[column] = "unknown"

    X = df[numeric_features + categorical_features].copy()

    X[numeric_features] = X[numeric_features].apply(pd.to_numeric, errors="coerce")

    if medians is None:
        medians = X[numeric_features].median()

    X[numeric_features] = X[numeric_features].fillna(medians)

    X[categorical_features] = X[categorical_features].fillna("unknown").astype(str)

    X = pd.get_dummies(X, columns=categorical_features, prefix=categorical_features, dummy_na=False)

    return X, medians


def main():
    print()
    print("=" * 60)
    print("PERSON 1 — FIRE TYPE CLASSIFIER v0")
    print("=" * 60)

    print()
    print("Loading dataset...")

    df = pd.read_csv(INPUT)

    print(f"Total rows in input: {len(df):,}")

    df = df[df["proposed_weak_class"].isin(LABELS)].copy()

    if len(df) == 0:
        raise RuntimeError("No weak-labelled rows found.")

    print(f"Rows used for training: {len(df):,}")

    print()
    print("Class distribution:")
    print(df["proposed_weak_class"].value_counts().to_string())

    print()
    print("Creating features...")

    df = add_features(df)

    y = df["proposed_weak_class"].astype(str)

    X, medians = make_X(df)

    print(f"Number of model features: {X.shape[1]}")

    print()
    print("Creating geographic train/test split...")

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)

    train_idx, test_idx = next(splitter.split(X, y, groups=df["spatial_group"]))

    print(f"Training rows: {len(train_idx):,}")
    print(f"Testing rows:  {len(test_idx):,}")

    print()
    print("Training Random Forest...")

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=18,
        min_samples_leaf=5,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=42
    )

    model.fit(X.iloc[train_idx], y.iloc[train_idx])

    print()
    print("Evaluating model...")

    predictions = model.predict(X.iloc[test_idx])

    report = classification_report(
        y.iloc[test_idx],
        predictions,
        labels=LABELS,
        output_dict=True,
        zero_division=0
    )

    balanced_accuracy = balanced_accuracy_score(y.iloc[test_idx], predictions)
    macro_f1 = f1_score(y.iloc[test_idx], predictions, average="macro")

    print()
    print("-" * 60)
    print("WEAK-LABEL TEST METRICS")
    print("IMPORTANT: these are NOT ground-truth accuracy.")
    print("-" * 60)

    print(f"Balanced accuracy: {balanced_accuracy:.4f}")
    print(f"Macro F1:          {macro_f1:.4f}")

    print()
    print("Per-class metrics:")

    for label in LABELS:
        print(f"{label:24s} precision={report[label]['precision']:.3f} recall={report[label]['recall']:.3f} F1={report[label]['f1-score']:.3f}")

    matrix = confusion_matrix(y.iloc[test_idx], predictions, labels=LABELS)

    print()
    print("Confusion matrix:")
    print("Rows = actual")
    print("Columns = predicted")
    print()
    print(pd.DataFrame(matrix, index=LABELS, columns=LABELS))

    print()
    print("Training final model on all weak-labelled data...")

    final_model = RandomForestClassifier(
        n_estimators=500,
        max_depth=18,
        min_samples_leaf=5,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=42
    )

    final_model.fit(X, y)

    joblib.dump(
        {
            "model": final_model,
            "feature_columns": list(X.columns),
            "numeric_medians": medians.to_dict(),
            "classes": list(final_model.classes_)
        },
        MODEL_OUT
    )

    print()
    print("Generating predictions for all events...")

    all_events = pd.read_csv(INPUT)
    all_events = add_features(all_events)

    X_all, _ = make_X(all_events, medians=pd.Series(medians))

    X_all = X_all.reindex(columns=X.columns, fill_value=False)

    probabilities = final_model.predict_proba(X_all)
    predicted_classes = final_model.predict(X_all)

    all_events["predicted_fire_type_v0"] = predicted_classes
    all_events["classification_confidence_v0"] = probabilities.max(axis=1)

    for i, class_name in enumerate(final_model.classes_):
        all_events[f"prob_{class_name}"] = probabilities[:, i]

    all_events.to_csv(PRED_OUT, index=False)

    metrics = pd.DataFrame(
        [
            {"metric": "test_rows", "value": len(test_idx)},
            {"metric": "balanced_accuracy", "value": balanced_accuracy},
            {"metric": "macro_f1", "value": macro_f1}
        ]
        + [
            {"metric": f"{label}_precision", "value": report[label]["precision"]}
            for label in LABELS
        ]
        + [
            {"metric": f"{label}_recall", "value": report[label]["recall"]}
            for label in LABELS
        ]
    )

    metrics.to_csv(METRICS_OUT, index=False)

    pd.DataFrame(matrix, index=LABELS, columns=LABELS).to_csv(CM_OUT)

    print()
    print("=" * 60)
    print("DONE!")
    print("=" * 60)
    print()
    print("Created:")
    print(f"  {MODEL_OUT}")
    print(f"  {PRED_OUT}")
    print(f"  {METRICS_OUT}")
    print(f"  {CM_OUT}")
    print()


if __name__ == "__main__":
    main()