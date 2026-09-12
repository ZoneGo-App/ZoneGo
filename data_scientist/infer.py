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

import os
import sys
import time
import joblib
import pandas as pd

from events import load_events_from_subgraph
from features import FEATURES_ALL, add_sequential_features, fit_aggregated_features, apply_aggregated_features

MODEL_BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.joblib")

# FIX (hallazgo del train.py con datos reales): los rasgos de grafo
# (covisit_partners, sybil_score, wallet_farm_signal) describen el ESTADO
# ACTUAL de la red de visitas -- no una generalización fija. Una billetera
# Sybil siempre es nueva por diseño del ataque, así que una referencia
# congelada en el momento del entrenamiento NUNCA la va a reconocer, sin
# importar qué tan bueno sea el modelo. Verificado: recall de
# repeated_nullifier caía de 100% a 0% con la referencia congelada.
#
# La solución no es el modelo -- es refrescar periódicamente la referencia
# contra todo lo indexado en el subgraph, tal como attack_simulation.py ya
# probó que funciona (su escenario "warm"). Esto es exactamente eso, pero
# corriendo de verdad en el camino de inferencia, con un caché por tiempo
# (TTL) para no recalcular en cada request.
REFERENCE_TTL_SECONDS = int(os.environ.get("ZONEGO_REFERENCE_TTL_SECONDS", "1800"))  # 30 min por defecto

_reference_cache = {"fitted": None, "fetched_at": 0.0, "subgraph_url": None}


def load_bundle() -> dict:
    if not os.path.exists(MODEL_BUNDLE_PATH):
        raise FileNotFoundError(
            f"{MODEL_BUNDLE_PATH} not found. Run `python3 train.py` first — "
            "it fits and saves this bundle (model + fallback feature reference + "
            "operating threshold) as its last step."
        )
    return joblib.load(MODEL_BUNDLE_PATH)


def get_operating_threshold(bundle: dict = None, point: str = "high_recall_point") -> float:
    if bundle is None:
        bundle = load_bundle()
    return bundle["threshold_info"][point]["threshold"]


def _get_refreshed_reference(subgraph_url: str, bundle: dict, ttl_seconds: int = REFERENCE_TTL_SECONDS) -> dict:
    """Devuelve la referencia de rasgos agregados (business_mode,
    covisits_train, graph_reference) recalculada sobre TODO lo indexado en
    el subgraph -- no la congelada del entrenamiento -- con un caché de
    `ttl_seconds` para no pagar el costo de recalcularla en cada request.

    Si el subgraph no responde, cae al fallback congelado guardado en el
    bundle (`bundle['fitted_features']`) en vez de tumbar el endpoint
    entero -- degradado en Sybil específicamente, pero sigue funcionando
    para los otros tres patrones de fraude, que no dependen de billeteras
    nunca vistas. Se imprime una advertencia explícita cuando esto pasa,
    porque es exactamente el escenario que el README documenta como "peor
    caso".
    """
    now = time.monotonic()
    cache_is_fresh = (
        _reference_cache["fitted"] is not None
        and _reference_cache["subgraph_url"] == subgraph_url
        and (now - _reference_cache["fetched_at"]) < ttl_seconds
    )
    if cache_is_fresh:
        return _reference_cache["fitted"]

    try:
        all_events = load_events_from_subgraph(subgraph_url)
        if all_events.empty:
            raise ValueError("subgraph returned zero indexed events")
        all_events = all_events.assign(**{"is_fraud": 0})  # placeholder, no se usa para fitear la referencia
        df = add_sequential_features(all_events)
        fitted = fit_aggregated_features(df)
    except Exception as exc:  # noqa: BLE001 — cualquier falla del subgraph cae al fallback, no debe tumbar el scoring
        print(f"WARNING: could not refresh graph reference from subgraph ({exc}). "
              f"Falling back to the frozen training-time reference — Sybil detection "
              f"specifically will be degraded until the next successful refresh.")
        return bundle['fitted_features']

    _reference_cache.update({"fitted": fitted, "fetched_at": now, "subgraph_url": subgraph_url})
    return fitted


def score_events(events_df: pd.DataFrame, bundle: dict = None, fitted_reference: dict = None) -> pd.DataFrame:
    """Scores a batch of live, UNLABELED events. `fitted_reference` should
    be the REFRESHED reference (see _get_refreshed_reference) whenever
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
    """The function api/routers/score.py's wallet_score() calls. Pulls ALL
    live events from the subgraph (needed to refresh the graph reference,
    not just this wallet's own events — the whole point is that
    covisit_partners/sybil_score are graph-wide facts), scores this
    wallet's events with the refreshed reference, and returns its most
    recent fraud score as a float in [0, 1], or None if the wallet has no
    indexed visits yet.
    """
    if bundle is None:
        bundle = load_bundle()

    events_df = load_events_from_subgraph(subgraph_url)
    if events_df.empty:
        return None

    wallet_events = events_df[events_df['wallet'].str.lower() == wallet.lower()]
    if wallet_events.empty:
        return None

    fitted_reference = _get_refreshed_reference(subgraph_url, bundle)
    scored = score_events(wallet_events, bundle=bundle, fitted_reference=fitted_reference)
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