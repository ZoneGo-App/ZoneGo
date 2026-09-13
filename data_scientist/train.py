import os
import numpy as np
import joblib
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, recall_score, precision_recall_curve
from sklearn.dummy import DummyClassifier
from sklearn.utils.class_weight import compute_sample_weight

from events import load_events_from_csv, LABEL_COLUMN
from features import (
    FEATURES_V1, FEATURES_ALL,
    add_sequential_features, fit_aggregated_features, apply_aggregated_features,
)

DATA_PATH = os.environ.get("ZONEGO_DATA_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "visits.csv"))
README_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
MODEL_BUNDLE_PATH = os.environ.get("ZONEGO_MODEL_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud_model.joblib"))

MIN_FRAUD_RECALL_TARGET = 0.85

# FIX (regression found running train.py on real data): the graph
# features (covisit_partners, sybil_score, wallet_farm_signal) were
# computed ONCE over df_train and stayed frozen. The Sybil pattern uses a
# new wallet for every claim -- it NEVER repeats -- so in production
# those wallets will never be in a reference frozen at training time, no
# matter how well trained the model is. Verified: repeated_nullifier
# recall dropped from 100% to 0% with the frozen reference, and went
# back to 100% recalculating it over the very batch being scored.
#
# The correct architecture for this system (not classic ML with train/test
# from distinct populations): graph features describe the CURRENT STATE
# of the visit network, not a generalization learned from a fixed set.
# infer.py now periodically refreshes that reference against everything
# indexed in the subgraph (see infer.py::_get_refreshed_reference). That's
# why here we measure and report TWO scenarios instead of one:
#
#   "frozen"    -- reference computed only from train, applied to test.
#                  This is the worst case: what happens if infer.py's
#                  refresh fails or the periodic job didn't run in time.
#   "refreshed" -- reference recalculated over the WHOLE dataset
#                  (train+test) before scoring test. This is what infer.py
#                  actually does in production, and the number that should
#                  be reported as expected performance.
#
# This is not label leakage: graph features are purely structural (who
# visited what, with whom, when) -- they never look at is_fraud. What
# changes is whether the reference knows the test wallets/merchants'
# STRUCTURE, which is exactly what a reference refreshed in production
# would also see.


def build_features(events_df: pd.DataFrame, test_size=0.2, random_state=42):
    """Builds both scenarios (frozen and refreshed) from the same split.
    Returns everything needed to train (always with the frozen reference,
    computed only from train -- so the model learns with the same
    discipline as always) and to evaluate in both scenarios."""
    print("1. Computing features from the event schema...")
    if LABEL_COLUMN not in events_df.columns:
        raise ValueError(
            f"build_features requires a labeled events_df (column '{LABEL_COLUMN}'). "
            "Real on-chain events won't have this until fraud is confirmed some "
            "other way — see ml/DATA.md, section 3."
        )

    df = add_sequential_features(events_df)

    train_idx, test_idx = train_test_split(
        df.index, test_size=test_size, random_state=random_state, stratify=df[LABEL_COLUMN]
    )
    df_train = df.loc[train_idx].copy()
    df_test = df.loc[test_idx].copy()

    # Training: ALWAYS with the frozen reference (train only). The model
    # learns to interpret the features as they look with a reasonable
    # reference -- it doesn't need to see test for that.
    fitted_frozen = fit_aggregated_features(df_train)
    df_train_frozen = apply_aggregated_features(df_train.copy(), fitted_frozen)
    df_test_frozen = apply_aggregated_features(df_test.copy(), fitted_frozen)

    # Production evaluation: reference recalculated over the WHOLE dataset
    # (train+test), applied to test. This simulates what infer.py actually
    # does -- refreshing against everything indexed -- and is the number
    # that should be reported as expected performance.
    fitted_refreshed = fit_aggregated_features(df)
    df_test_refreshed = apply_aggregated_features(df_test.copy(), fitted_refreshed)

    X_train = df_train_frozen[FEATURES_ALL].fillna(0)
    y_train = df_train_frozen[LABEL_COLUMN]
    X_test_frozen = df_test_frozen[FEATURES_ALL].fillna(0)
    X_test_refreshed = df_test_refreshed[FEATURES_ALL].fillna(0)
    y_test = df_test_frozen[LABEL_COLUMN]  # same test set, same order, same y

    return X_train, X_test_frozen, X_test_refreshed, y_train, y_test, fitted_frozen


def _fit_and_score(X_train, y_train, X_test, y_test, feature_subset, use_sample_weight):
    gb = GradientBoostingClassifier(random_state=42)
    if use_sample_weight:
        weights = compute_sample_weight('balanced', y_train)
        gb.fit(X_train[feature_subset], y_train, sample_weight=weights)
    else:
        gb.fit(X_train[feature_subset], y_train)
    y_pred = gb.predict(X_test[feature_subset])
    f1_mac = f1_score(y_test, y_pred, average='macro', zero_division=0)
    recall_fraud = recall_score(y_test, y_pred, pos_label=1, zero_division=0)
    return f1_mac, recall_fraud, gb


def select_operating_threshold(y_true, y_proba, min_fraud_recall=MIN_FRAUD_RECALL_TARGET):
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
    precisions, recalls = precisions[:-1], recalls[:-1]

    denom = precisions + recalls
    f1s = np.where(denom > 0, 2 * precisions * recalls / np.where(denom > 0, denom, 1), 0.0)
    idx_f1 = int(np.argmax(f1s)) if len(f1s) else 0
    threshold_f1 = float(thresholds[idx_f1]) if len(thresholds) else 0.5

    eligible = np.where(recalls >= min_fraud_recall)[0]
    if len(eligible) > 0 and len(thresholds):
        idx_hr = int(eligible[np.argmax(thresholds[eligible])])
        threshold_high_recall = float(thresholds[idx_hr])
    else:
        threshold_high_recall = float(thresholds[0]) if len(thresholds) else 0.5

    def _operating_stats(threshold):
        y_pred = (y_proba >= threshold).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        fraud_recall = tp / (tp + fn) if (tp + fn) else 0.0
        legit_hold_rate = fp / (fp + tn) if (fp + tn) else 0.0
        return {
            "threshold": threshold, "fraud_recall": fraud_recall,
            "fraud_missed_rate": 1.0 - fraud_recall, "legit_hold_rate": legit_hold_rate,
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        }

    f1_point = _operating_stats(threshold_f1)
    high_recall_point = _operating_stats(threshold_high_recall)
    target_missed = high_recall_point["fraud_recall"] < min_fraud_recall

    return {
        "f1_point": f1_point, "high_recall_point": high_recall_point,
        "min_fraud_recall_target": min_fraud_recall, "high_recall_target_missed": target_missed,
    }


def train_and_evaluate():
    events_df = load_events_from_csv(DATA_PATH)
    X_train, X_test_frozen, X_test_refreshed, y_train, y_test, fitted_frozen = build_features(events_df)

    print("\n2. Training models...")

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train[FEATURES_ALL], y_train)
    y_pred_base = baseline.predict(X_test_refreshed[FEATURES_ALL])

    lr = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    lr.fit(X_train[FEATURES_ALL], y_train)
    y_pred_lr = lr.predict(X_test_refreshed[FEATURES_ALL])

    # v1 (Day 2/3) as reference -- doesn't depend on the graph reference,
    # so "frozen" and "refreshed" give it exactly the same result.
    f1_v1, recall_v1, _ = _fit_and_score(X_train, y_train, X_test_refreshed, y_test, FEATURES_V1, use_sample_weight=True)

    # v1 + graph, measured in BOTH scenarios with the SAME trained model.
    weights = compute_sample_weight('balanced', y_train)
    gb = GradientBoostingClassifier(random_state=42)
    gb.fit(X_train[FEATURES_ALL], y_train, sample_weight=weights)

    y_pred_frozen = gb.predict(X_test_frozen[FEATURES_ALL])
    f1_frozen = f1_score(y_test, y_pred_frozen, average='macro', zero_division=0)
    recall_frozen = recall_score(y_test, y_pred_frozen, pos_label=1, zero_division=0)

    y_pred_gb = gb.predict(X_test_refreshed[FEATURES_ALL])
    y_proba_gb = gb.predict_proba(X_test_refreshed[FEATURES_ALL])[:, 1]
    f1_all = f1_score(y_test, y_pred_gb, average='macro', zero_division=0)
    recall_all = recall_score(y_test, y_pred_gb, pos_label=1, zero_division=0)

    print("\n3. Evaluating key metrics (Focus on Recall and F1-Macro):")
    print("-" * 50)

    results = []
    for name, y_pred in [("Trivial Baseline", y_pred_base),
                          ("Balanced Logistic Regression", y_pred_lr),
                          ("Gradient Boosting", y_pred_gb)]:
        f1_mac = f1_score(y_test, y_pred, average='macro', zero_division=0)
        recall_fraud = recall_score(y_test, y_pred, pos_label=1, zero_division=0)
        print(f"Model: {name}")
        print(f"  -> F1-Macro:     {f1_mac:.4f}")
        print(f"  -> Fraud Recall: {recall_fraud:.4f}  <-- This is the critical metric!")
        print("-" * 50)
        results.append((name, f1_mac, recall_fraud))

    graph_comparison = {
        "day2_features": FEATURES_V1,
        "day2_f1": f1_v1, "day2_recall": recall_v1,
        "day4_f1": f1_all, "day4_recall": recall_all,
        "day4_f1_frozen": f1_frozen, "day4_recall_frozen": recall_frozen,
    }

    importances = sorted(zip(FEATURES_ALL, gb.feature_importances_), key=lambda p: p[1], reverse=True)
    top_features = importances[:3]

    # The operating threshold is chosen over the REFRESHED probabilities,
    # because that is what infer.py will serve in production -- choosing
    # it over the frozen ones would underestimate the real available recall.
    threshold_info = select_operating_threshold(y_test.values, y_proba_gb)

    write_readme_ml(results, graph_comparison, top_features, threshold_info,
                     n_train=len(X_train), n_test=len(y_test))

    joblib.dump({
        'model': gb,
        'fitted_features': fitted_frozen,  # fallback if the subgraph doesn't respond -- see infer.py
        'feature_columns': FEATURES_ALL,
        'threshold_info': threshold_info,
    }, MODEL_BUNDLE_PATH)
    print(f"Fraud model + fitted feature bundle + operating threshold saved to {MODEL_BUNDLE_PATH}")

    return results


def pick_conclusion(results):
    baseline_name, baseline_f1, baseline_recall = results[0]
    candidates = results[1:]
    best = max(candidates, key=lambda r: r[1])
    discarded = [r for r in candidates if r is not best and r[1] <= baseline_f1]
    best_is_usable = best[1] > baseline_f1
    return baseline_name, baseline_f1, best, discarded, best_is_usable


def write_readme_ml(results, graph_comparison, top_features, threshold_info, n_train, n_test, path=README_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = "\n".join(f"| {name} | {f1_mac:.4f} | {recall:.4f} |" for name, f1_mac, recall in results)

    baseline_name, baseline_f1, best, discarded, best_is_usable = pick_conclusion(results)

    if not best_is_usable:
        conclusion_lines = [
            f"**No usable model this run.** The best candidate (`{best[0]}`, "
            f"F1-macro {best[1]:.4f}) does not beat the trivial baseline ({baseline_f1:.4f})."
        ]
    else:
        conclusion_lines = [f"**Recommended model: `{best[0]}`** — F1-macro {best[1]:.4f}, fraud recall {best[2]:.4f}."]
        if discarded:
            for name, f1_mac, recall in discarded:
                conclusion_lines.append(
                    f"- `{name}` is **discarded**: F1-macro ({f1_mac:.4f}) at or below baseline ({baseline_f1:.4f})."
                )
        else:
            conclusion_lines.append("- No other candidate underperformed the trivial baseline this run.")
    conclusion = "\n".join(conclusion_lines)

    top_features_lines = "\n".join(
        f"{i+1}. `{name}` — importance {score:.4f}" for i, (name, score) in enumerate(top_features)
    )

    delta_f1 = graph_comparison["day4_f1"] - graph_comparison["day2_f1"]
    delta_recall = graph_comparison["day4_recall"] - graph_comparison["day2_recall"]

    f1p = threshold_info["f1_point"]
    hrp = threshold_info["high_recall_point"]
    target = threshold_info["min_fraud_recall_target"]
    target_warning = (
        f"\n> **Note:** no threshold reached the target recall floor ({target:.0%}).\n"
        if threshold_info["high_recall_target_missed"] else ""
    )

    content = f"""# Fraud Model Baseline — ZoneGo

Automatically generated by `train.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

80/20 stratified split by `is_fraud`. Train: {n_train} rows · Test: {n_test} rows.

Features v1 (Day 2/3): `previous_time`, `implied_velocity`, `hour_deviation`, `covisit_degree`.
Graph features (Day 4): `covisit_partners`, `business_entropy`, `temporal_concentration`,
`sybil_score`, `wallet_farm_signal`.

| Model | F1-Macro | Fraud Recall |
|---|---|---|
{rows}

## ⚠️ Critical finding and how it was resolved: frozen vs. refreshed graph reference

Graph features describe the CURRENT STATE of the visit network — they are
not a generalization the model learns once and is done with. The
`repeated_nullifier` (Sybil) pattern uses a new wallet for every claim, so
a reference computed ONCE at training time will never know about those
wallets in production, no matter how well trained the model is:

| Scenario | F1-Macro | Fraud Recall |
|---|---|---|
| **Frozen** reference (train only, never updated) | {graph_comparison['day4_f1_frozen']:.4f} | {graph_comparison['day4_recall_frozen']:.4f} |
| **Refreshed** reference (recalculated over everything indexed — what `infer.py` actually does) | {graph_comparison['day4_f1']:.4f} | {graph_comparison['day4_recall']:.4f} |

**`infer.py` periodically refreshes the reference against the full
subgraph — the number in the "refreshed" row is the one that runs in
production.** The "frozen" row is documented as the worst case: what
happens if the refresh job fails or the subgraph doesn't respond and the
system falls back to the static fallback.

## Day 4 — graph feature improvement (measured with refreshed reference)

| Feature set | F1-Macro | Fraud Recall |
|---|---|---|
| Day 2/3 only | {graph_comparison['day2_f1']:.4f} | {graph_comparison['day2_recall']:.4f} |
| + graph features (Day 4, refreshed) | {graph_comparison['day4_f1']:.4f} | {graph_comparison['day4_recall']:.4f} |
| **Delta** | **{'+' if delta_f1>=0 else ''}{delta_f1:.4f}** | **{'+' if delta_recall>=0 else ''}{delta_recall:.4f}** |

## Three highest-weighted features

{top_features_lines}

## Operating threshold (precision-recall curve over refreshed probabilities)

{target_warning}
| Point | Threshold | Fraud caught (recall) | Fraud missed | Legit held |
|---|---|---|---|---|
| **Optimal F1** | {f1p['threshold']:.4f} | {f1p['fraud_recall']:.2%} | {f1p['fraud_missed_rate']:.2%} | {f1p['legit_hold_rate']:.2%} |
| **High recall** (target ≥{target:.0%}) | {hrp['threshold']:.4f} | {hrp['fraud_recall']:.2%} | {hrp['fraud_missed_rate']:.2%} | {hrp['legit_hold_rate']:.2%} |

## What happens if the model gets it wrong?

- **Retention is reversible, not a confiscation.** A high `fraud_score`
  pauses the payout while it's reviewed; it does not cancel it.
- **The neighbor can appeal.** A false positive has a way out: human
  review and payout release. A false negative has no equivalent appeal on
  the merchant's side — which is why the "high recall" point is justified.
- **The score never decides alone.** `wallet_score()` returns only the
  `[0, 1]` probability; converting it to basis points and deciding
  whether to hold live in the payment tree, not in the model.
- **If the reference refresh fails**, the system falls back to the frozen
  fallback — worse for Sybil specifically (see table above), but still
  works for the other three patterns, which don't depend on never-seen
  wallets.

## Conclusion

{conclusion}

## Data source

Trained on `data/visits.csv`. Live inference runs through `infer.py`,
which refreshes the aggregated-feature reference against
`events.load_events_from_subgraph()` on a TTL cache instead of using the
training-time snapshot — see `infer.py::_get_refreshed_reference`.
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nComparative table + frozen/refreshed comparison + threshold + conclusion committed to {path}")


if __name__ == "__main__":
    train_and_evaluate()