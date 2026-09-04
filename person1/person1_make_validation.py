import pandas as pd

INPUT = "person1_fire_type_classification_worldcover.csv"
OUTPUT = "person1_independent_validation_60.csv"

df = pd.read_csv(INPUT)

if "proposed_weak_class" in df.columns:
    LABEL_COL = "proposed_weak_class"
elif "weak_label" in df.columns:
    LABEL_COL = "weak_label"
else:
    raise ValueError(f"Could not find the weak-label column. Available columns are: {list(df.columns)}")

print("Using label column:", LABEL_COL)
print()

classes = ["industrial_proxy", "forest_proxy", "other_natural_proxy"]
samples = []

for cls in classes:
    data = df[df[LABEL_COL] == cls].copy()

    print(f"{cls}: {len(data)} available")

    if len(data) < 20:
        raise ValueError(f"Not enough rows for {cls}. Only {len(data)} available.")

    if "frp" in data.columns:
        data["frp"] = pd.to_numeric(data["frp"], errors="coerce")

    valid_frp = "frp" in data.columns and data["frp"].notna().sum() >= 20 and data.loc[data["frp"].notna(), "frp"].nunique() >= 3

    if valid_frp:
        frp_data = data[data["frp"].notna()].copy()

        try:
            frp_data["frp_bin"] = pd.qcut(frp_data["frp"], q=10, labels=False, duplicates="drop")
            selected = []

            for _, group in frp_data.groupby("frp_bin", observed=True):
                n = min(2, len(group))
                selected.append(group.sample(n=n, random_state=42))

            selected = pd.concat(selected)

        except Exception:
            selected = data.sample(n=20, random_state=42)

    else:
        selected = data.sample(n=20, random_state=42)

    if len(selected) < 20:
        remaining = data.drop(selected.index, errors="ignore")
        needed = 20 - len(selected)

        if len(remaining) >= needed:
            extra = remaining.sample(n=needed, random_state=42)
            selected = pd.concat([selected, extra])
        else:
            selected = data.sample(n=20, random_state=42)

    else:
        selected = selected.sample(n=20, random_state=42)

    samples.append(selected)

validation = pd.concat(samples, ignore_index=True)
validation = validation.sample(frac=1, random_state=42).reset_index(drop=True)

validation.insert(0, "validation_id", [f"VT{i:03d}" for i in range(1, len(validation) + 1)])

validation["satellite_map"] = validation.apply(lambda r: f"https://www.google.com/maps/@?api=1&map_action=map&center={r.latitude},{r.longitude}&zoom=17&basemap=satellite", axis=1)
validation["firms_map"] = validation.apply(lambda r: f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{r.longitude},{r.latitude},12z", axis=1)
validation["earth"] = validation.apply(lambda r: f"https://earth.google.com/web/@{r.latitude},{r.longitude},1500a,1200d,35y,0h,0t,0r", axis=1)

validation["manual_label"] = ""
validation["manual_confidence"] = ""
validation["manual_notes"] = ""

validation.to_csv(OUTPUT, index=False)

print()
print("=" * 60)
print("PERSON 1 — INDEPENDENT VALIDATION SET")
print("=" * 60)
print()
print("Total events:", len(validation))
print()
print("Sampling buckets:")
print(validation[LABEL_COL].value_counts().to_string())
print()
print("Created:", OUTPUT)
print()
print("=" * 60)
print("NEXT STEP")
print("=" * 60)
print()
print("Open the CSV in Excel.")
print()
print("Fill manual_label with:")
print("  INDUSTRIAL")
print("  FOREST")
print("  OTHER_NATURAL")
print("  UNCERTAIN")
print()
print("Fill manual_confidence with:")
print("  HIGH")
print("  MEDIUM")
print("  LOW")
print()
print("DO NOT use the weak label as your answer.")