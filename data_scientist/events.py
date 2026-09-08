"""
Canonical visit-event schema for ZoneGo's fraud pipeline.
"""

import pandas as pd
import requests

# Every event, regardless of source, must be normalized to exactly these
# columns before it reaches build_features(). `lat`/`lon` are resolved from
# the campaign's registered business location (they are not literally part
# of the on-chain VisitRecorded event, which only carries campaignId,
# visitor, nullifierHash, timestamp, sigHash) — that resolution is the
# loader's job, not the feature pipeline's.
EVENT_SCHEMA = [
    "visit_id",       # str       - unique visit/tx identifier
    "wallet",         # str       - visitor's wallet address (on-chain `visitor`)
    "nullifier",      # str       - stable per-human nullifier hash (World ID)
    "business_id",    # str       - merchant identifier (resolved from campaignId)
    "business_type",  # str       - merchant category, for the rubro classifier
    "lat",            # float     - merchant latitude
    "lon",            # float     - merchant longitude
    "timestamp",      # datetime  - block timestamp of VisitRecorded
]

# Only present on labeled/synthetic data. Real on-chain events won't carry
# this until fraud is confirmed some other way (see ml/DATA.md, section 3).
LABEL_COLUMN = "is_fraud"

_VISITS_QUERY= """
query GetVisits($first: Int!, $skip: Int!) {
  visits(first: $first, skip: $skip, orderBy: timestamp, orderDirection: asc) {
    id
    visitor { id }
    merchant { id }
    nullifierHash
    timestamp
    campaign { geohash }
  }
}
"""




def _validate_schema(df: pd.DataFrame, require_label: bool = False) -> None:
    required = list(EVENT_SCHEMA) + ([LABEL_COLUMN] if require_label else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Events are missing required schema columns: {missing}")


def load_events_from_csv(path: str, require_label: bool = True) -> pd.DataFrame:
    """Adapter: synthetic/exported CSV -> canonical event schema."""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    _validate_schema(df, require_label=require_label)
    cols = list(EVENT_SCHEMA) + ([LABEL_COLUMN] if require_label else [])
    return df[cols].copy()


def load_events_from_subgraph(subgraph_url: str, page_size: int = 1000, max_pages: int = 50) -> pd.DataFrame:
    """Adapter stub: subgraph (GraphQL) -> canonical event schema."""

    rows=[]
    for page in range(max_pages):
        skip =page*page_size
        resp = requests.post(
            subgraph_url,
            json={"query": _VISITS_QUERY, "variables": {"first":page_size, "skip":skip}},
            timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Subgraph returned errors: {payload['errors']}")
        visits = payload.get("data", {}).get("visits", [])
        if not visits:
            break
        for v in visits:
            merchant = v.get("merchant") or {}
            campaign = v.get("campaign") or {}
            
            # Decodificación del geohash de la campaña para obtener lat/lon
            lat, lon = 0.0, 0.0
            raw_geohash = campaign.get("geohash")
            if raw_geohash:
                try:
                    from utils import decode_geohash
                    lat, lon = decode_geohash(raw_geohash)
                except ImportError:
                    pass  # Si la función está en otro módulo, ajústala aquí

            rows.append({
                "visit_id": v.get("id"),
                "wallet": v.get("visitor", {}).get("id"),
                "nullifier": v.get("nullifierHash"),
                "business_id": merchant.get("id", "unknown"),
                "business_type": "unknown",  # No viene en cadena por ahora
                "lat": float(lat),
                "lon": float(lon),
                "timestamp": pd.to_datetime(int(v.get("timestamp", 0)), unit="s"),
            })

        if len(visits) < page_size:
            break  # Última página

    df = pd.DataFrame(rows, columns=EVENT_SCHEMA)
    _validate_schema(df, require_label=False)
    return df
