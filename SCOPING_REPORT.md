# Scoping Report — Fire Existence Detector

## 1. Branch A vs. Branch B Distinction

The detector is split into two branches based on a fundamental data availability asymmetry:

**Branch A (Industrial Facility Pipeline):** Hotspot detections within 500m of a known industrial facility are evaluated against that facility's own historical baseline. Industrial sites produce routine thermal signatures (refineries, power plants, chemical works) that would trigger naive threshold detectors. Branch A learns each facility's normal operating range and flags deviations — not absolute heat, but *unexpected* heat for that specific location.

**Branch B (Open-Area Fallback):** Hotspots that do not match any known facility lack a location-specific history to compare against. Instead, Branch B compares each detection's VIIRS attributes (FRP, brightness temperatures, scan geometry) against the *population* of all open-area detections in the region. This is a deliberate scoping decision: it can identify attribute-wise outliers (e.g., unusually intense or large-footprint events) but cannot detect whether a particular forest patch or field has "abnormal" fire activity relative to its own history, because no such history is maintained.

**Why this split:** Treating all hotspots uniformly would either (a) miss industrial anomalies because the baseline FRP in a refinery cluster is naturally high, or (b) flood open-area detections with false positives from facilities. The split lets each branch apply the appropriate detection logic.

---

## 2. Minimum-History Cutoff and Cold-Start Handling

Facilities with **fewer than 60 observed days** in the VIIRS record do not receive a per-facility Isolation Forest model. This threshold is a pragmatic choice: with fewer observations, rolling statistics (30-day windows) and anomaly models produce unstable, unreliable baselines.

**Cold-start handling:** Low-history facilities are grouped into a **pooled model** — a single Isolation Forest trained on the combined feature vectors of all low-history facilities. This provides a weaker but still meaningful anomaly signal: a detection is flagged if its feature vector is unusual *relative to the pool of similar under-observed facilities*, rather than relative to its own (insufficient) history.

The statistical z-score baseline still operates on whatever history is available, even if short, as a secondary signal.

---

## 3. Why Deep Learning Was Not Used

- **Data volume:** VIIRS produces a sparse, tabular time series per facility (one row per facility-day). This is a classic tabular anomaly detection problem, not a perception or sequence-modeling problem where deep learning excels.
- **Label scarcity:** No ground-truth fire/non-fire labels exist for this region and period. Unsupervised methods (Isolation Forest, z-score thresholds) are the natural fit. Training a supervised deep model would require labeled data we don't have.
- **Interpretability:** The statistical baseline (z-score, percentile) and Isolation Forest scores are directly interpretable. A neural network's anomaly score would be a black box, harder to debug and explain to stakeholders.
- **Timeline:** The project deadline does not justify the engineering overhead of deep learning infrastructure for a problem where established statistical methods are well-suited.

---

## 4. Synthetic Anomaly Injection Evaluation (Caveat)

The evaluation in Step 16 uses **synthetic anomaly injection**, not real labeled fire events. This means:

- **What it validates:** The detector's ability to identify FRP spikes and count surges relative to a facility's historical baseline. If injected spikes are recovered with high precision/recall, the detection logic is functioning correctly.
- **What it does NOT validate:** Whether real-world industrial fires produce the specific spike signatures we inject. Real fires may have subtler, multi-day signatures or different spatial patterns.
- **Why this is acceptable:** No labeled fire incident dataset exists for this region and timeframe. The synthetic injection test is standard practice in anomaly detection when ground-truth labels are unavailable. It demonstrates the pipeline's sensitivity and false-positive rate under controlled conditions.

---

## 5. Population-Level Nature of Branch B

Branch B's Isolation Forest operates on the **regional population** of all open-area detections, not on per-location history. This means:

- It can flag a detection as unusual *compared to the typical open-area hotspot in Gujarat's Golden Corridor*.
- It **cannot** flag a detection as unusual *for a specific field or forest patch* — there is no per-location baseline.
- This is a deliberate design choice, not an oversight. Building per-grid-cell history for the entire region would require a dense spatial grid, significantly more storage, and a longer historical window than currently available.

**Implication for downstream use:** Branch B's "fire detected" flag indicates *statistically unusual thermal activity in the regional context*, not *confirmed fire at a previously fire-free location*. The downstream fire-type classifier should weight Branch B flags with this context in mind.

---

## 6. Technical Specifications

| Parameter | Value |
|---|---|
| Region | Gujarat Golden Corridor (21.20°N–22.40°N, 72.60°E–73.40°E) |
| Data source | VIIRS SNPP 375m (NASA FIRMS) |
| Facility buffer | 500m radius (UTM 42N projection) |
| Minimum history | 60 observed days |
| Rolling window | 30 days |
| Robust z-score threshold | 3.0 |
| Hotspot count percentile | 95th |
| IF contamination | 0.05 |
| IF estimators | 100 |
| Severity levels | HIGH, MEDIUM, LOW |
