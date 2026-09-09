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


LABEL_COLUMN = "is_fraud"
# Real mapping:
#   business_id   -> merchant.id (denormalized directly onto Visit)
#   lat / lon     -> decoded from campaign.geohash (see _decode_geohash below)
#   business_type -> does not exist on-chain yet. Stays "unknown" until the
#                    team decides where merchant category/description lives.

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

_GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def _decode_geohash(geohash: str) -> tuple:
     """Standard base32 geohash -> (lat, lon) decoding. Public, well-known
        algorithm, implemented here from scratch (no external geohash
        dependency needed for this one conversion).
    """
     lat_range = [-90.0, 90.0]
     lon_range = [-180.0, 180.0]
     event_bit = True
     for char in geohash:
        idx = _GEOHASH_BASE32.index(char)
        for bit_pos in range(4, -1, -1):
            bit = (idx >> bit_pos) & 1
            target = lon_range if event_bit else lat_range
            mid = (target[0] + target[1]) / 2
            if bit:
                target[0] = mid
            else:
                target[1] = mid
                even_bit = not even_bit
        lat = (lat_range[0] + lat_range[1]) / 2
        lon = (lon_range[0] + lon_range[1]) / 2
        return lat, lon

def _bytes32_to_geohash_string(hex_value: str) -> str:
   
    hex_value = hex_value[2:] if hex_value.startswith("0x") else hex_value
    raw = bytes.fromhex(hex_value)
    return raw.rstrip(b"\x00").decode("ascii", errors="ignore")

def _resolve_lat_lon(geohash_value) -> tuple:
    
    if not geohash_value or not isinstance(geohash_value, str):
        raise ValueError(f"empty or non-string geohash: {geohash_value!r}")
    try:
        if geohash_value.startswith("0x"):
            geohash_value = _bytes32_to_geohash_string(geohash_value)
        if not geohash_value:
            raise ValueError("geohash decoded to an empty string")
        return _decode_geohash(geohash_value)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"could not decode geohash {geohash_value!r}: {exc}") from exc

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
    skipped = 0
    for page in range(max_pages):
        skip =page * page_size
        try:
            resp = requests.post(
            subgraph_url,
            json={"query": _VISITS_QUERY, "variables": {"first":page_size, "skip":skip}},
            timeout=30
        )
            resp.raise_for_status()
        except requests.exceptions.RequestException as Exc:
            raise RuntimeError(f'Subgraph request failed (page {page}, skip {skip}')
        
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Subgraph returned errors: {payload['errors']}")
        
        visits = payload["data"]["visits"]
        if not visits:
            break

        for v in visits:
            try:
                lat, lon = _resolve_lat_lon(v["campaign"]["geohash"])
                rows.append({
                    "visit_id": v["id"],
                    "wallet": v["visitor"]["id"],
                    "nullifier": v["nullifierHash"],
                    "business_id": v["merchant"]["id"],  # denormalized directly on Visit
                    "business_type": "unknown",           # not on-chain yet — see Observation #9
                    "lat": lat,
                    "lon": lon,
                        "timestamp": pd.to_datetime(int(v["timestamp"]), unit="s"),
                    })
            except (KeyError, TypeError, ValueError) as exc:
                skipped += 1
                visit_id = v.get("id", "<unknown>") if isinstance(v, dict) else "<unknown>"
                print(f"WARNING: skipping visit {visit_id} — {exc}")
        
            if len(visits) < page_size:
                    break  # last page
        
        if skipped:
            print(f"load_events_from_subgraph: skipped {skipped} malformed visit(s) out of {skipped + len(rows)} fetched")
        
        df = pd.DataFrame(rows, columns=EVENT_SCHEMA)
        _validate_schema(df, require_label=False)
        return df