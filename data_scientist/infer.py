from __future__ import annotations

import os
import sys
import joblib
import pandas as pd

from events import load_events_from_subgraph
from features import FEATURES_ALL, add_sequential_features, apply_aggregated_features

MODEL_BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.joblib")


def load_bundle() -> dict:
    if not os.path.exists(MODEL_BUNDLE_PATH):
        raise FileNotFoundError(
            f"{MODEL_BUNDLE_PATH} not found. Run `python3 train.py` first — "
            "it fits and saves this bundle (model + fitted feature aggregates + "
            "operating threshold) as its last step."
        )
    return joblib.load(MODEL_BUNDLE_PATH)


def get_operating_threshold(bundle: dict = None, point: str = "high_recall_point") -> float:
   
    if bundle is None:
        bundle = load_bundle()
    return bundle["threshold_info"][point]["threshold"]


def score_events(events_df: pd.DataFrame, bundle: dict = None) -> pd.DataFrame:
    """Scores a batch of live, UNLABELED events. Returns events_df with a
    `fraud_score` column appended (P(is_fraud=1) from the trained model).
    Uses the exact aggregates train.py fit on the training split — nothing
    here is re-derived from the live batch itself, which is what makes this
    safe to call on a single wallet's handful of visits and still get a
    meaningful modal_hour / covisit_degree / graph-feature value.
    """
    if bundle is None:
        bundle = load_bundle()

    if events_df.empty:
        return events_df.assign(fraud_score=pd.Series(dtype=float))

    df = add_sequential_features(events_df)
    df = apply_aggregated_features(df, bundle['fitted_features'])
    X = df[bundle['feature_columns']].fillna(0)
    proba = bundle['model'].predict_proba(X)[:, 1]
    df['fraud_score'] = proba
    return df


def score_wallet(wallet: str, subgraph_url: str, bundle: dict = None) -> float | None:
    """The function api/routers/score.py's wallet_score() should call.
    Pulls LIVE events from the subgraph for the given wallet and returns its
    most recent fraud score as a plain float in [0, 1], or None if the
    wallet has no indexed visits yet. This is the actual call site
    """
    if bundle is None:
        bundle = load_bundle()

    events_df = load_events_from_subgraph(subgraph_url)
    if events_df.empty:
        return None

    wallet_events = events_df[events_df['wallet'].str.lower() == wallet.lower()]
    if wallet_events.empty:
        return None

    scored = score_events(wallet_events, bundle=bundle)
    latest = scored.sort_values('timestamp').iloc[-1]
    return float(latest['fraud_score'])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 infer.py <subgraph_url> <wallet_address>")
        sys.exit(1)

    subgraph_url_arg, wallet_arg = sys.argv[1], sys.argv[2]
    score = score_wallet(wallet_arg, subgraph_url_arg)
    if score is None:
        print(f"No indexed visits found for {wallet_arg}")
    else:
        print(f"fraud_score for {wallet_arg}: {score:.4f}")