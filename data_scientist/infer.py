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

# Todo se resuelve relativo a este mismo archivo -- no importa en qué
# carpeta viva el proyecto (no se asume "ml/", "backend/", ni ningún otro
# nombre). ZONEGO_MODEL_PATH permite apuntar a otro lado si hace falta.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_BUNDLE_PATH = os.environ.get("ZONEGO_MODEL_PATH", os.path.join(_BASE_DIR, "fraud_model.joblib"))

# FIX (hallazgo del train.py con datos reales): los rasgos de grafo
# (covisit_partners, sybil_score, wallet_farm_signal) describen el ESTADO
# ACTUAL de la red de visitas -- no una generalización fija. Una billetera
# Sybil siempre es nueva por diseño del ataque, así que una referencia
# congelada en el momento del entrenamiento NUNCA la va a reconocer, sin
# importar qué tan bueno sea el modelo. Verificado: recall de
# repeated_nullifier caía de 100% a 0% con la referencia congelada.
REFERENCE_TTL_SECONDS = int(os.environ.get("ZONEGO_REFERENCE_TTL_SECONDS", "1800"))  # 30 min por defecto

# `events` y el cursor (`cursor_timestamp`/`cursor_id`) viven en el mismo
# caché que la referencia fiteada -- ver _get_cached_snapshot() para el
# porqué de cada campo.
_reference_cache = {
    "fitted": None,
    "events": None,
    "fetched_at": 0.0,
    "subgraph_url": None,
    "cursor_timestamp": 0,
    "cursor_id": "",
}

# FIX (reportado por el equipo, corrida real contra el subgraph): el
# except amplio de abajo caía al fallback congelado con solo un print() --
# invisible en cualquier setup de logs de producción real, justo en el
# escenario donde Sybil se degrada de 100% a 0% de recall. Ahora se loguea
# con logging.error() (nivel que sí se captura en la mayoría de configs) Y
# se guarda en este dict, consultable desde afuera (ej. un endpoint de
# healthcheck) sin tener que parsear logs.
_degraded_state = {"is_degraded": False, "since": None, "reason": None}


def is_reference_degraded() -> dict:
    """Devuelve el estado de degradación actual -- para un endpoint de
    healthcheck o un dashboard, sin depender de que alguien esté mirando
    los logs en el momento exacto en que el subgraph falló."""
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
    """UNA sola función que trae del subgraph, cachea, y a la que TANTO
    score_wallet() como el fiteo de la referencia recurren -- no hay
    ningún otro lugar en este archivo que llame a load_events_from_subgraph().

    FIX #1 (reportado, corrida real): antes score_wallet() llamaba a
    load_events_from_subgraph() directo y SIN protección para traer los
    eventos de la wallet, y por separado _get_refreshed_reference() la
    volvía a llamar si el caché estaba frío -- hasta DOS traídas completas
    por request, y el detector de degradación (_degraded_state) solo vivía
    en la segunda, así que la falla más común (la primera traída, sin try/
    except, reventando antes de llegar a la segunda) nunca lo prendía.
    Con una sola función protegida como único punto de entrada, ambos
    problemas se resuelven a la vez: no puede haber una traída sin marcar
    el estado, porque ya no existe ninguna traída fuera de acá.

    FIX #2 (refresco incremental de verdad, no solo el nombre): cada
    refresco pide `since_timestamp`/`since_id` = el cursor del refresco
    anterior, no repite el historial completo. El cursor avanza al último
    (timestamp, id) que trajo la traída incremental, y los eventos nuevos
    se concatenan sobre el caché existente (deduplicados por `visit_id`
    por si el borde exacto del cursor se repite). Con la cuota de Studio
    en mente: una vez que el caché tiene algo, cada refresco de acá en
    adelante paga solo por lo que pasó en los últimos `ttl_seconds`, sin
    importar qué tan grande sea el historial total acumulado.

    Orden de degradación si la traída incremental falla:
      1. Si ya había un caché de este mismo subgraph, se sirve tal cual
         (mejor que fallar la request por un tropiezo pasajero) y se marca
         `is_degraded=True` igual, para que un healthcheck lo vea aunque
         la request en curso haya salido bien.
      2. Si no hay ningún caché todavía, se relanza la excepción -- que es
         justo lo que score.py ya convierte en un 502 correcto -- pero
         ahora SIEMPRE pasando antes por _mark_degraded(), a diferencia de
         antes.
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

    Right now this will return None for basically any real wallet: the
    deployed subgraph has zero indexed visits until the contracts get
    redeployed (blocked on that, not on this code) — validate against
    data/visits.csv (the synthetic set) in the meantime.
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
