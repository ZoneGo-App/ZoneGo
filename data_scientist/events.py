"""
Canonical visit-event schema for ZoneGo's fraud pipeline.

The whole point of freezing this schema (Día 1 of the plan) is that
`build_features()` in train.py never has to change when the data source
changes. Today the only loader is the synthetic CSV; once Lucio's subgraph
(Día 4) is live, `load_events_from_subgraph()` becomes the real loader and
nothing downstream is touched, because both return the exact same columns.
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


#
# Real mapping:
#   business_id   -> merchant.id (denormalized directly onto Visit)
#   lat / lon     -> decoded from campaign.geohash (see _decode_geohash below)
#   business_type -> does not exist on-chain yet. Stays "unknown" until the
#                    team decides where merchant category/description lives
#       
_VISITS_QUERY = """
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
    even_bit = True
    for char in geohash:
        idx = _GEOHASH_BASE32.index(char)
        for bit_pos in range(4, -1, -1):
            bit = (idx >> bit_pos) & 1
            target = lon_range if even_bit else lat_range
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
    """Adapter: synthetic/exported CSV: event schema.

    This is the TRAINING data source (generate.py's output). It exists so
    the CSV's column names/order are an implementation detail of ONE loader,
    never something build_features() depends on directly.
    """
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    _validate_schema(df, require_label=require_label)
    cols = list(EVENT_SCHEMA) + ([LABEL_COLUMN] if require_label else [])
    return df[cols].copy()


def load_events_from_subgraph(subgraph_url: str, page_size: int = 1000, max_pages: int = 50) -> pd.DataFrame:
    """Adapter: subgraph (GraphQL) -> canonical event schema.

    This is the LIVE data source. The Graph's requirement is textual:
    inference for the demo must run against the subgraph, not a local or
    simulated dataset — the CSV/generate.py path is for TRAINING only. This
    function is that path: it paginates `visits` from a real deployed
    subgraph and returns the exact same columns load_events_from_csv()
    does (minus `is_fraud`, which doesn't exist for real events yet), so
    build_features() and every model downstream run unmodified either way.

    HARDENING: each visit is parsed independently now. A single visit with
    a missing `campaign`/`merchant`/`visitor` relationship, or a geohash
    that fails to decode, is skipped (with a printed warning) instead of
    raising and discarding the entire page's worth of otherwise-good
    visits. If MANY rows are being skipped, that's a real data-quality
    signal worth investigating (see the printed summary at the end) — not
    something to silently swallow either.

    NOTE: field names here now match the ACTUAL deployed subgraph
    (api.studio.thegraph.com/query/1758817/zone-go/v0.0.1) as reported in
    the Día 4 code review — this was wrong before (see Observation #2) and
    would have failed on the first real call. Still: I have not run this
    against that live endpoint myself — this sandbox has no network access
    to thegraph.com. The geohash decoding in particular (_resolve_lat_lon)
    is my best guess at the encoding convention, not confirmed against
    Sebastián's contract; verify the very first batch of decoded
    coordinates land inside the actual campaign's neighborhood before
    trusting this in the demo.
    """
    rows = []
    skipped = 0
    for page in range(max_pages):
        skip = page * page_size
        try:
            resp = requests.post(
                subgraph_url,
                json={"query": _VISITS_QUERY, "variables": {"first": page_size, "skip": skip}},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Subgraph request failed (page {page}, skip {skip}): {exc}") from exc

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
