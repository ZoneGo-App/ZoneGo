from __future__ import annotations

import os
import sys
import time
import logging
import joblib
import pandas as pd

from events import load_events_from_subgraph
from features import FEATURES_ALL, add_sequential_features, fit_aggregated_features, apply_aggregated_features

logger = logging.getLogger("zonego.infer")

# Everything is resolved relative to this file -- it doesn't matter what
# folder the project lives in (no assumption of "ml/", "backend/", or any
# other name). ZONEGO_MODEL_PATH lets you point elsewhere if needed.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_BUNDLE_PATH = os.environ.get("ZONEGO_MODEL_PATH", os.path.join(_BASE_DIR, "fraud_model.joblib"))

# FIX (finding from running train.py on real data): the graph features
# (covisit_partners, sybil_score, wallet_farm_signal) describe the CURRENT
# state of the visit network -- not a fixed generalization. A Sybil wallet
# is always new by the attack's design, so a reference frozen at training
# time will NEVER recognize it in production, no matter how well trained
# the model is. Verified: repeated_nullifier recall dropped from 100% to
# 0% with the frozen reference.
REFERENCE_TTL_SECONDS = int(os.environ.get("ZONEGO_REFERENCE_TTL_SECONDS", "1800"))  # 30 min by default

# `events` and the cursor (`cursor_timestamp`/`cursor_id`) live in the
# same cache as the fitted reference -- see _get_cached_snapshot() for why
# each field is there.
_reference_cache = {
    "fitted": None,
    "events": None,
    "fetched_at": 0.0,
    "subgraph_url": None,
    "cursor_timestamp": 0,
    "cursor_id": "",
}

# FIX (reported by the team, real run against the subgraph): the broad
# except below used to fall back to the frozen fallback with just a
# print() -- invisible in any real production logging setup, right in the
# exact scenario where Sybil detection degrades from 100% to 0% recall.
# Now it's logged with logging.error() (a level that actually gets
# captured in most configs) AND stored in this dict, queryable from the
# outside (e.g. a healthcheck endpoint) without having to parse logs.
_degraded_state = {"is_degraded": False, "since": None, "reason": None}


def is_reference_degraded() -> dict:
    """Returns the current degradation state -- for a healthcheck endpoint
    or a dashboard, without depending on someone watching the logs at the
    exact moment the subgraph failed."""
    return dict(_degraded_state)


def load_bundle() -> dict:
    if not os.path.exists(MODEL_BUNDLE_PATH):
        raise FileNotFoundError(
            f"{MODEL_BUNDLE_PATH} not found. Run `python3 train.py` first — "
            "it fits and saves this bundle (model + fitted feature reference + "
            "operating threshold) as its last step."
        )
    return joblib.load(MODEL_BUNDLE_PATH)


def get_operating_threshold(bundle: dict = None, point: str = "high_recall_point") -> float:
    if bundle is None:
        bundle = load_bundle()
    return bundle["threshold_info"][point]["threshold"]


def _mark_degraded(reason: str) -> None:
    _degraded_state.update({"is_degraded": True, "since": time.time(), "reason": reason})


def _mark_recovered() -> None:
    if _degraded_state["is_degraded"]:
        logger.info("Graph reference refresh recovered — no longer running on the frozen fallback.")
    _degraded_state.update({"is_degraded": False, "since": None, "reason": None})


def _get_cached_snapshot(subgraph_url: str, bundle: dict, ttl_seconds: int = REFERENCE_TTL_SECONDS) -> dict:
    """A SINGLE function that fetches from the subgraph, caches, and is
    used by BOTH score_wallet() and the reference fitting step -- there is
    no other place in this file that calls load_events_from_subgraph().

    FIX #1 (reported, real run): before, score_wallet() called
    load_events_from_subgraph() directly and UNPROTECTED to fetch the
    wallet's events, and separately _get_refreshed_reference() called it
    AGAIN if the cache was cold -- up to TWO full fetches per request, and
    the degradation detector (_degraded_state) only lived in the second
    one, so the most common failure (the first fetch, with no try/except,
    blowing up before ever reaching the second) never triggered it. With a
    single protected function as the only entry point, both problems are
    solved at once: there can be no fetch without marking the state,
    because there is no longer any fetch outside of here.

    FIX #2 (real incremental refresh, not just the name): each refresh
    asks for `since_timestamp`/`since_id` = the previous refresh's cursor,
    instead of repeating the whole history. The cursor advances to the
    last (timestamp, id) the incremental fetch brought back, and the new
    events get concatenated onto the existing cache (deduplicated by
    `visit_id` in case the exact cursor boundary repeats). With Studio's
    quota in mind: once the cache has something, every refresh from here
    on only pays for what happened in the last `ttl_seconds`, no matter
    how large the total accumulated history is.

    Degradation order if the incremental fetch fails:
      1. If there was already a cache for this same subgraph, serve it as
         is (better than failing the request over a transient hiccup) and
         still mark `is_degraded=True`, so a healthcheck can see it even
         if the current request went fine.
      2. If there is no cache yet at all, re-raise the exception -- which
         is exactly what score.py already turns into a proper 502 -- but
         now ALWAYS going through _mark_degraded() first, unlike before.
    """
    now = time.monotonic()
    cache_is_fresh = (
        _reference_cache["events"] is not None
        and _reference_cache["subgraph_url"] == subgraph_url
        and (now - _reference_cache["fetched_at"]) < ttl_seconds
    )
    if cache_is_fresh:
        return _reference_cache

    same_subgraph = _reference_cache["events"] is not None and _reference_cache["subgraph_url"] == subgraph_url
    since_ts = _reference_cache["cursor_timestamp"] if same_subgraph else 0
    since_id = _reference_cache["cursor_id"] if same_subgraph else ""

    try:
        new_events = load_events_from_subgraph(subgraph_url, since_timestamp=since_ts, since_id=since_id)
    except Exception as exc:
        logger.error(
            "Could not fetch new events from the subgraph (%s). Falling back to the frozen "
            "training-time reference — Sybil detection specifically will be degraded until "
            "the next successful refresh.", exc, exc_info=True,
        )
        _mark_degraded(str(exc))
        if same_subgraph:
            logger.warning(
                "Serving the snapshot fetched %.0fs ago instead of failing this request.",
                now - _reference_cache["fetched_at"],
            )
            return _reference_cache
        raise

    if same_subgraph:
        all_events = pd.concat([_reference_cache["events"], new_events], ignore_index=True)
        all_events = all_events.drop_duplicates(subset="visit_id", keep="last")
        cursor_timestamp, cursor_id = _reference_cache["cursor_timestamp"], _reference_cache["cursor_id"]
    else:
        all_events = new_events
        cursor_timestamp, cursor_id = 0, ""

    if not new_events.empty:
        last_row = new_events.sort_values("timestamp").iloc[-1]
        cursor_timestamp = int(last_row["timestamp"].timestamp())
        cursor_id = last_row["visit_id"]

    if all_events.empty:
        logger.warning("Subgraph returned zero indexed events; using the frozen training-time reference.")
        fitted = bundle['fitted_features']
        _mark_degraded("subgraph has zero indexed events")
    else:
        try:
            df = add_sequential_features(all_events.assign(**{"is_fraud": 0}))  # placeholder, not used to fit
            fitted = fit_aggregated_features(df)
            _mark_recovered()
        except Exception as exc:  # noqa: BLE001 — a fit failure degrades Sybil detection, it shouldn't break scoring
            logger.error(
                "Could not fit a refreshed reference from %d cached events (%s). Falling back "
                "to the frozen training-time reference.", len(all_events), exc, exc_info=True,
            )
            _mark_degraded(str(exc))
            fitted = bundle['fitted_features']

    _reference_cache.update({
        "fitted": fitted,
        "events": all_events,
        "fetched_at": now,
        "subgraph_url": subgraph_url,
        "cursor_timestamp": cursor_timestamp,
        "cursor_id": cursor_id,
    })
    return _reference_cache


def score_events(events_df: pd.DataFrame, bundle: dict = None, fitted_reference: dict = None) -> pd.DataFrame:
    """Scores a batch of live, UNLABELED events. `fitted_reference` should
    be the REFRESHED reference (see _get_cached_snapshot) whenever
    possible — falling back to bundle['fitted_features'] only degrades
    Sybil-style detection, it doesn't break the other three patterns.
    """
    if bundle is None:
        bundle = load_bundle()
    if fitted_reference is None:
        fitted_reference = bundle['fitted_features']

    if events_df.empty:
        return events_df.assign(fraud_score=pd.Series(dtype=float))

    df = add_sequential_features(events_df)
    df = apply_aggregated_features(df, fitted_reference)
    X = df[bundle['feature_columns']].fillna(0)
    proba = bundle['model'].predict_proba(X)[:, 1]
    df['fraud_score'] = proba
    return df


def score_wallet(wallet: str, subgraph_url: str, bundle: dict = None) -> float | None:
    """The function score.py's wallet_score() calls. Uses the SAME cached,
    incrementally-refreshed snapshot (see _get_cached_snapshot) for both
    this wallet's own events and the refreshed graph reference — never
    calls load_events_from_subgraph() directly, so there is no
    unprotected fetch path left in this file. Returns the wallet's most
    recent fraud score as a float in [0, 1], or None if it has no indexed
    visits yet.

    Right now this will return None for basically any real wallet: campaign
    1 at Delancey is indexed and funded, but zero visits have landed yet
    (waiting on Sebas to make the first one, not blocked on this code) —
    validate against data/visits.csv (the synthetic set) in the meantime.
    """
    if bundle is None:
        bundle = load_bundle()

    snapshot = _get_cached_snapshot(subgraph_url, bundle)
    all_events = snapshot["events"]
    if all_events is None or all_events.empty:
        return None

    wallet_events = all_events[all_events['wallet'].str.lower() == wallet.lower()]
    if wallet_events.empty:
        return None

    scored = score_events(wallet_events, bundle=bundle, fitted_reference=snapshot["fitted"])
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