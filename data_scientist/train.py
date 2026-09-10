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

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "visits.csv")
README_PATH = os.path.join(os.path.dirname(__file__), "README.md")

# FIX (Observations #4 + #5): the trained model AND the fitted feature
# bundle (business_mode, covisits_train, graph_reference) are saved
# together. Without this, nothing downstream had anything to load: no
# predict(), no persisted model, and even if one existed, the graph
# features had no fitted reference to compute from at inference time.
# infer.py loads this exact file — see MODEL_BUNDLE_PATH there.
MODEL_BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.joblib")

# Once retention is reversible and appealable (see write_readme_ml's FAQ
# section), the cost of a false positive is "a neighbor waits and appeals,"
# not "a neighbor permanently loses funds." That asymmetry is why the
# high-recall operating point below is allowed to trade away some legit
# convenience for fraud recall — it is not a free parameter, it is a
# consequence of the appeal policy actually existing.
MIN_FRAUD_RECALL_TARGET = 0.85


def build_features(events_df: pd.DataFrame, test_size=0.2, random_state=42):
    """Builds features from an already-normalized events DataFrame (see
    events.EVENT_SCHEMA) and returns a train/test split plus the fitted
    feature bundle (needed to persist for inference — see train_and_evaluate).
    Never reads a CSV itself — that is the loader's job. Synthetic and real
    events run through this exact same function, unmodified.

    Leak-safety: the split happens BEFORE every aggregated feature (modal
    hour, co-visit degree, and all graph features, including sybil_score)
    is computed. Only `previous_time` and `implied_velocity` are computed
    on the whole frame (add_sequential_features), because they depend
    solely on each entity's own past, not on any dataset-wide aggregate.
    """
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

    fitted = fit_aggregated_features(df_train)
    df_train = apply_aggregated_features(df_train, fitted)
    df_test = apply_aggregated_features(df_test, fitted)

    X_train = df_train[FEATURES_ALL].fillna(0)
    y_train = df_train[LABEL_COLUMN]
    X_test = df_test[FEATURES_ALL].fillna(0)
    y_test = df_test[LABEL_COLUMN]

    return X_train, X_test, y_train, y_test, fitted


def _fit_and_score(X_train, y_train, X_test, y_test, feature_subset, use_sample_weight):
    """Trains a GradientBoostingClassifier on exactly `feature_subset` and
    returns (f1_macro, recall_fraud, fitted_model). Reused to produce both
    the Day 2/3-only baseline and the full Day 4 feature-set result, so the
    "improvement over the Day 2 baseline" comparison is measured with the
    same model and the same split, not pulled from an old README.
    """
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
    """Picks the score cutoff from the precision-recall curve instead of
    eyeballing one.

    Two candidate operating points are computed and BOTH are reported —
    the choice of which one actually gates a hold belongs to whoever owns
    the payout tree, not to this script:

    - `f1_point`: the threshold that maximizes F1 on the fraud class — the
      balanced pick, without favoring recall or precision.
    - `high_recall_point`: the highest threshold (i.e. most permissive on
      holding funds) that still keeps fraud recall at or above
      `min_fraud_recall`. This is the "lean toward catching fraud" pick —
      it is only defensible BECAUSE a hold is reversible and appealable
      (see write_readme_ml's FAQ section); if holds were final, this
      trade-off would not be acceptable.

    Returns a dict with both points' threshold and confusion-derived
    operating stats (fraud recall, fraud missed, legit hold rate).
    """
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
    # precision_recall_curve returns one more precision/recall point than
    # thresholds (it appends the (precision=1, recall=0) endpoint), so drop
    # the last precision/recall entry to align them with `thresholds`.
    precisions, recalls = precisions[:-1], recalls[:-1]

    denom = precisions + recalls
    f1s = np.where(denom > 0, 2 * precisions * recalls / np.where(denom > 0, denom, 1), 0.0)
    idx_f1 = int(np.argmax(f1s)) if len(f1s) else 0
    threshold_f1 = float(thresholds[idx_f1]) if len(thresholds) else 0.5

    eligible = np.where(recalls >= min_fraud_recall)[0]
    if len(eligible) > 0 and len(thresholds):
        # Among thresholds that still hit the recall floor, pick the
        # HIGHEST one — that holds as FEW legitimate wallets as possible
        # while still catching at least `min_fraud_recall` of the fraud.
        idx_hr = int(eligible[np.argmax(thresholds[eligible])])
        threshold_high_recall = float(thresholds[idx_hr])
    else:
        # No threshold in this run reaches the target recall — fall back to
        # the most permissive threshold available and flag it plainly in
        # the report rather than silently returning a point that lies.
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
            "threshold": threshold,
            "fraud_recall": fraud_recall,
            "fraud_missed_rate": 1.0 - fraud_recall,
            "legit_hold_rate": legit_hold_rate,
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        }

    f1_point = _operating_stats(threshold_f1)
    high_recall_point = _operating_stats(threshold_high_recall)
    target_missed = high_recall_point["fraud_recall"] < min_fraud_recall

    return {
        "f1_point": f1_point,
        "high_recall_point": high_recall_point,
        "min_fraud_recall_target": min_fraud_recall,
        "high_recall_target_missed": target_missed,
    }


def train_and_evaluate():
    events_df = load_events_from_csv(DATA_PATH)
    X_train, X_test, y_train, y_test, fitted = build_features(events_df)

    print("\n2. Training models...")

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train[FEATURES_ALL], y_train)
    y_pred_base = baseline.predict(X_test[FEATURES_ALL])

    lr = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    lr.fit(X_train[FEATURES_ALL], y_train)
    y_pred_lr = lr.predict(X_test[FEATURES_ALL])

    # Day 2/3 baseline vs Day 4 (v1 + graph, incl. sybil_score / wallet_farm_signal),
    # same sample_weight treatment on both so the comparison isolates only
    # the feature-set change.
    f1_v1, recall_v1, _ = _fit_and_score(X_train, y_train, X_test, y_test, FEATURES_V1, use_sample_weight=True)
    f1_all, recall_all, gb = _fit_and_score(X_train, y_train, X_test, y_test, FEATURES_ALL, use_sample_weight=True)
    y_pred_gb = gb.predict(X_test[FEATURES_ALL])
    y_proba_gb = gb.predict_proba(X_test[FEATURES_ALL])[:, 1]

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
        "day2_f1": f1_v1,
        "day2_recall": recall_v1,
        "day4_f1": f1_all,
        "day4_recall": recall_all,
    }

    importances = sorted(
        zip(FEATURES_ALL, gb.feature_importances_), key=lambda p: p[1], reverse=True
    )
    top_features = importances[:3]

    # Threshold selection (Day 4 wrap-up item): from the precision-recall
    # curve of the CHOSEN model (gb) on the held-out test set, never from
    # eyeballing a round number like 0.5.
    threshold_info = select_operating_threshold(y_test.values, y_proba_gb)

    write_readme_ml(
        results, graph_comparison, top_features, threshold_info,
        n_train=len(X_train), n_test=len(X_test),
    )

    # FIX (Observations #3 + #4 + #5): persist the trained model TOGETHER
    # with the fitted feature bundle AND the chosen operating threshold(s).
    # Without the feature bundle, wallet_score() in api/routers/score.py
    # has nothing to load. The threshold is stored here so whoever owns
    # the payout tree / basis-points conversion can read it instead of
    # hardcoding a number in the API layer — wallet_score() itself still
    # returns only the raw probability, never a hold/no-hold decision.
    joblib.dump({
        'model': gb,
        'fitted_features': fitted,
        'feature_columns': FEATURES_ALL,
        'threshold_info': threshold_info,
    }, MODEL_BUNDLE_PATH)
    print(f"Fraud model + fitted feature bundle + operating threshold saved to {MODEL_BUNDLE_PATH}")

    return results


def pick_conclusion(results):
    """Picks a recommended model and flags any candidate that performs at or
    below the trivial baseline — including the winner itself, not just the
    discarded candidates."""
    baseline_name, baseline_f1, baseline_recall = results[0]
    candidates = results[1:]

    best = max(candidates, key=lambda r: r[1])
    discarded = [r for r in candidates if r is not best and r[1] <= baseline_f1]

    best_is_usable = best[1] > baseline_f1
    return baseline_name, baseline_f1, best, discarded, best_is_usable


def write_readme_ml(results, graph_comparison, top_features, threshold_info, n_train, n_test, path=README_PATH):
    """Commits the comparative metrics table, the Day 4 graph-features
    improvement, the top-3 explanatory features, the precision-recall-curve
    operating threshold, the appeal/reversibility policy, AND a written
    conclusion to /ml/README.md."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = "\n".join(
        f"| {name} | {f1_mac:.4f} | {recall:.4f} |"
        for name, f1_mac, recall in results
    )

    baseline_name, baseline_f1, best, discarded, best_is_usable = pick_conclusion(results)

    if not best_is_usable:
        conclusion_lines = [
            f"**No usable model this run.** The best candidate (`{best[0]}`, "
            f"F1-macro {best[1]:.4f}) does not beat the trivial baseline "
            f"({baseline_f1:.4f}). Do not ship any of these."
        ]
    else:
        conclusion_lines = [
            f"**Recommended model: `{best[0]}`** — F1-macro {best[1]:.4f}, fraud recall {best[2]:.4f}."
        ]
        if discarded:
            for name, f1_mac, recall in discarded:
                conclusion_lines.append(
                    f"- `{name}` is **discarded**: its F1-macro ({f1_mac:.4f}) is at or "
                    f"below the trivial baseline ({baseline_f1:.4f}). In production this "
                    f"would freeze payouts for a large share of honest neighbors — not usable."
                )
        else:
            conclusion_lines.append("- No other candidate underperformed the trivial baseline this run.")

    conclusion = "\n".join(conclusion_lines)

    top_features_lines = "\n".join(
        f"{i+1}. `{name}` — importance {score:.4f}" for i, (name, score) in enumerate(top_features)
    )

    delta_f1 = graph_comparison["day4_f1"] - graph_comparison["day2_f1"]
    delta_recall = graph_comparison["day4_recall"] - graph_comparison["day2_recall"]
    delta_sign = "+" if delta_f1 >= 0 else ""
    delta_recall_sign = "+" if delta_recall >= 0 else ""

    f1p = threshold_info["f1_point"]
    hrp = threshold_info["high_recall_point"]
    target = threshold_info["min_fraud_recall_target"]
    target_warning = (
        f"\n> **Note:** no threshold in this run reached the target recall "
        f"floor ({target:.0%}); the high-recall point shown below is the "
        f"most permissive available, not a guarantee of {target:.0%}.\n"
        if threshold_info["high_recall_target_missed"] else ""
    )

    content = f"""# Fraud Model Baseline — ZoneGo

Automatically generated by `train.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

80/20 stratified split by `is_fraud`, split performed **before** every
aggregated feature (modal hour, co-visit degree, and all graph features) is
computed, so no test-set information leaks into training.
Train: {n_train} rows · Test: {n_test} rows.

Features v1 (Day 2/3): `previous_time`, `implied_velocity`, `hour_deviation`, `covisit_degree`.
Graph features (Day 4, subgraph-only): `covisit_partners`, `business_entropy`,
`temporal_concentration`, `sybil_score` (World's Sybil signal — how many other
wallets share this wallet's nullifier), and `wallet_farm_signal` (the two
combined: sybil reuse × co-visit degree).

| Model | F1-Macro | Fraud Recall |
|---|---|---|
{rows}

## Day 4 — improvement from graph-indexed features

Same Gradient Boosting model, same split, evaluated with and without the
graph-only features (including the Sybil / wallet-farm signal):

| Feature set | F1-Macro | Fraud Recall |
|---|---|---|
| Day 2/3 only (`{"`, `".join(graph_comparison["day2_features"])}`) | {graph_comparison["day2_f1"]:.4f} | {graph_comparison["day2_recall"]:.4f} |
| + graph features incl. Sybil score (Day 4) | {graph_comparison["day4_f1"]:.4f} | {graph_comparison["day4_recall"]:.4f} |
| **Delta** | **{delta_sign}{delta_f1:.4f}** | **{delta_recall_sign}{delta_recall:.4f}** |

## Three highest-weighted features

{top_features_lines}

## Operating threshold (precision-recall curve, not eyeballed)

Chosen on the precision-recall curve of `Gradient Boosting` on the test set,
not with a round number like 0.5. TWO points are calculated and documented —
which of the two triggers a real hold in the payment tree is a product
decision, not a script decision:
{target_warning}
| Point | Threshold | Fraud detected (recall) | Fraud missed | Legitimate holds |
|---|---|---|---|---|
| **Optimal F1** (balanced) | {f1p['threshold']:.4f} | {f1p['fraud_recall']:.2%} | {f1p['fraud_missed_rate']:.2%} | {f1p['legit_hold_rate']:.2%} |
| **High recall** (target ≥{target:.0%} of fraud caught) | {hrp['threshold']:.4f} | {hrp['fraud_recall']:.2%} | {hrp['fraud_missed_rate']:.2%} | {hrp['legit_hold_rate']:.2%} |

The "high recall" point is only defensible because the hold is
reversible (see section below) — if holding were final, this
trade-off would not be acceptable.

## What happens if the model is wrong?

- **The hold is reversible, not a confiscation.** A high `fraud_score`
  pauses the payment while under review; it does not cancel it or redirect it
  to another account. The neighbor doesn't lose funds just for being flagged.
- **The neighbor can appeal.** A false positive (holding someone legitimate)
  has an exit: human review and payment release. A false negative
  (letting real fraud pass) has no equivalent appeal from the affected merchant's
  side — which is why the "high recall" threshold above is justified: it's
  cheaper for the system for a legitimate user to wait and appeal than to let
  fraud pass unaddressed.
- **The score never decides alone.** `wallet_score()` in the API returns
  only the probability `[0, 1]`; the conversion to basis points and the
  decision of what to do with it live in the payment tree logic, not in the
  model. This leaves a human control point between "the model suspects" and
  "the payment is held".

## Conclusion

{conclusion}

> Fraud class recall is the critical metric: letting fraud slip through costs merchant revenue.

## Data source

Trained on `data/visits.csv` (`events.load_events_from_csv`). Live inference
runs through `infer.py`, which calls `events.load_events_from_subgraph()`
instead — The Graph's requirement is live data, not this training CSV. The
trained model + fitted feature bundle + operating threshold used by
`infer.py` / `api/routers/score.py` are saved to `ml/fraud_model.joblib` by
this script.
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nComparative table + Day 4 comparison + operating threshold + conclusion committed to {path}")


if __name__ == "__main__":
    train_and_evaluate()