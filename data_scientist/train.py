import os
import pandas as pd 
import joblib
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, recall_score, precision_recall_curve
from sklearn.dummy import DummyClassifier
from sklearn.utils.class_weight import compute_sample_weight
from events import load_events_from_csv, LABEL_COLUMN



DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "visits.csv")
README_PATH = os.path.join(os.path.dirname(__file__), "README.md")

FEATURES = ['previous_time', 'implied_velocity', 'hour_deviation', 'covisit_degree']


def build_features(events_df: pd.DataFrame, test_size=0.2, random_state=42):
    """Builds features from an already-normalized events DataFrame (see
    events.EVENT_SCHEMA) and returns a train/test split. Never reads a CSV
    itself — that is the loader's job (events.load_events_from_csv today,
    events.load_events_from_subgraph once Día 4 lands). Synthetic and real
    events run through this exact same function, unmodified.

    IMPORTANT: the split happens BEFORE the two aggregated features
    (modal operating hour, co-visit degree) are computed, so no test-set
    information leaks into training. `previous_time` and `implied_velocity`
    are not affected: they only look at each wallet's own past history, not
    at dataset-wide aggregates.
    """
    print("1. Computing features v1 from the event schema...")
    if LABEL_COLUMN not in events_df.columns:
        raise ValueError(
            f"build_features requires a labeled events_df (column '{LABEL_COLUMN}'). "
            "Real on-chain events won't have this until fraud is confirmed some "
            "other way — see ml/DATA.md, section 3."
        )

    df = events_df.copy()
    df['hour'] = df['timestamp'].dt.hour
    #Calculate the preceding time grouped by NULLIFIER (sorted strictly by nullifier and time).
    df = df.sort_values(by=['nullifier', 'timestamp']).reset_index(drop=True)
    df['previous_time'] = df.groupby('nullifier')['timestamp'].diff().dt.total_seconds().fillna(999999)#
    #Calculate spatial displacements grouped by wallet (sorted by wallet and time).
    df = df.sort_values(by=['wallet', 'timestamp']).reset_index(drop=True)
    df['lat_prev'] = df.groupby('wallet')['lat'].shift(1).fillna(df['lat'])
    df['lon_prev'] = df.groupby('wallet')['lon'].shift(1).fillna(df['lon'])
    #Features derived from distance and speed
    df['approx_distance'] = np.sqrt((df['lat'] - df['lat_prev']) ** 2 + ((df['lon'] - df['lon_prev']) * np.cos(np.radians(df['lat']))) ** 2)
    df['implied_velocity'] = df['approx_distance'] / (df['previous_time'] + 1)
    df['hour_window'] = df['timestamp'].dt.floor('h')

    # --- Split BEFORE computing the aggregated features ---
    train_idx, test_idx = train_test_split(
        df.index, test_size=test_size, random_state=random_state, stratify=df[LABEL_COLUMN]
    )
    df_train = df.loc[train_idx].copy()
    df_test = df.loc[test_idx].copy()

    global_mode_hour = df_train['hour'].mode()[0]
    business_mode = (
        df_train.groupby('business_id')['hour']
        .agg(lambda x: x.mode()[0] if not x.empty else global_mode_hour)
        .rename('modal_hour')
    )
    covisits_train = (
        df_train.groupby(['business_id', 'hour_window'])['wallet']
        .nunique()
        .rename('covisit_degree')
        .reset_index()
    )

    def apply_aggregated_features(subset):
        subset = subset.merge(business_mode, on='business_id', how='left')
        subset['modal_hour'] = subset['modal_hour'].fillna(global_mode_hour)
        subset['hour_deviation'] = np.abs(subset['hour'] - subset['modal_hour'])

        subset = subset.merge(covisits_train, on=['business_id', 'hour_window'], how='left')
        # A business/hour combo unseen in training looks like an isolated visit.
        subset['covisit_degree'] = subset['covisit_degree'].fillna(1)
        return subset

    df_train = apply_aggregated_features(df_train)
    df_test = apply_aggregated_features(df_test)

    X_train = df_train[FEATURES].fillna(0)
    y_train = df_train[LABEL_COLUMN]
    X_test = df_test[FEATURES].fillna(0)
    y_test = df_test[LABEL_COLUMN]

    return X_train, X_test, y_train, y_test


def train_and_evaluate():
    events_df = load_events_from_csv(DATA_PATH)
    X_train, X_test, y_train, y_test = build_features(events_df)

    print("\n2. Training models...")

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train, y_train)
    y_pred_base = baseline.predict(X_test)

    lr = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)
    #primary model responsible for learning complex fraud patterns 
    # (such as impossible travel or coordinated visits) in order to distinguish 
    # them from normal behavior.
    gb = GradientBoostingClassifier(random_state=42)
    sample_weights = compute_sample_weight('balanced', y_train)
    gb.fit(X_train, y_train, sample_weight=sample_weights)
    y_pred_gb = gb.predict(X_test)

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

    write_readme_ml(results, n_train=len(X_train), n_test=len(X_test))
    return results


def pick_conclusion(results):
    """Picks a recommended model and flags any candidate that performs at or
    below the trivial baseline — the exact case the review caught with
    Logistic Regression scoring a lower F1-macro than doing nothing."""
    baseline_name, baseline_f1, baseline_recall = results[0]
    candidates = results[1:]

    best = max(candidates, key=lambda r: r[1])  # highest F1-macro
    discarded = [r for r in candidates if r is not best and r[1] <= baseline_f1]

    # A case where the best model does not outperform the baseline
    if best[1] <= baseline_f1:
        conclusion_lines = [
            f"**No usable model this run.** The best candidate "
            f"(`{best[0]}`, F1-macro {best[1]:.4f}) does not beat the "
            f"trivial baseline ({baseline_f1:.4f})."
        ]
        return baseline_name, baseline_f1, best, discarded, conclusion_lines

    # Standard case where a recommended model exists.
    conclusion_lines = [
        f"**Recommended model: `{best[0]}`** — F1-macro {best[1]:.4f}, fraud recall {best[2]:.4f}."
    ]
    if discarded:
        for name, f1_mac, recall in discarded:
            verdict = "at or below" if f1_mac <= baseline_f1 else "close to"
            conclusion_lines.append(
                f"- `{name}` is **discarded**: its F1-macro ({f1_mac:.4f}) is {verdict} "
                f"the trivial baseline ({baseline_f1:.4f}). In production this would "
                f"freeze payouts for a large share of honest neighbors — not usable."
            )
    else:
        conclusion_lines.append(
            "- No other candidate underperformed the trivial baseline this run."
        )

    return baseline_name, baseline_f1, best, discarded, conclusion_lines


def write_readme_ml(results, n_train, n_test, path=README_PATH):
    """Commits the comparative metrics table AND a written conclusion to
    /ml/README.md — which model is recommended and why any other candidate
    is discarded, instead of leaving a bare table with no verdict."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = "\n".join(
        f"| {name} | {f1_mac:.4f} | {recall:.4f} |"
        for name, f1_mac, recall in results
    )

    # Recibimos los 5 valores correctamente
    baseline_name, baseline_f1, best, discarded, conclusion_lines = pick_conclusion(results)
    conclusion = "\n".join(conclusion_lines)

    content = f"""# Fraud Model Baseline — ZoneGo

Automatically generated by `train.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

80/20 stratified split by `is_fraud`, split performed **before** the aggregated
features (`hour_deviation`, `covisit_degree`) are computed, so no test-set
information leaks into training. Train: {n_train} rows · Test: {n_test} rows.

Features v1: `previous_time`, `implied_velocity`, `hour_deviation`, `covisit_degree`.

| Model | F1-Macro | Fraud Recall |
|---|---|---|
{rows}

## Conclusion

{conclusion}

> Fraud class recall is the critical metric: letting fraud slip through costs merchant revenue.
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nComparative table + conclusion committed to {path}")


if __name__ == "__main__":
    train_and_evaluate()
