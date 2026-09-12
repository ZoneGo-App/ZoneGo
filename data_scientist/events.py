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
query GetVisits($first: Int!, $lastTimestamp: BigInt!, $lastId: String!) {
  visits(
    first: $first
    orderBy: timestamp
    orderDirection: asc
    where: {
      or: [
        { timestamp_gt: $lastTimestamp }
        { timestamp: $lastTimestamp, id_gt: $lastId }
      ]
    }
  ) {
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


def load_events_from_subgraph(
    subgraph_url: str,
    page_size: int = 1000,
    max_pages: int = 1000,
    since_timestamp: int = 0,
    since_id: str = "",
) -> pd.DataFrame:
    """Adapter: subgraph (GraphQL) -> canonical event schema.

    This is the LIVE data source. The Graph's requirement is textual:
    inference for the demo must run against the subgraph, not a local or
    simulated dataset — the CSV/generate.py path is for TRAINING only.

    FIX (real bug found running this against the live subgraph, reported
    directly by the team): the previous skip-based pagination
    (`skip: $skip`) is not a soft limit — The Graph rejects `skip > 5000`
    with a hard GraphQL error, not an empty page. With page_size=1000 that
    breaks on page 6 (skip=6000), roughly 8x earlier than the 50,000-row
    ceiling this function's docstring used to (wrongly) claim. Worse: that
    error is a RuntimeError, which score.py's wallet_score() catches and
    turns into an HTTP 502 for EVERY wallet, not just during a reference
    refresh — score_wallet() also calls this function directly to fetch a
    target wallet's own events. Any subgraph with more than ~6,000 indexed
    visits took the whole endpoint down, both on cold start (empty cache)
    and on periodic refresh.

    The fix is cursor-based pagination: track the LAST row's (timestamp,
    id) from each page and ask for `timestamp_gt` that value, with an
    `id_gt` tiebreaker for the case where more than `page_size` visits
    share the exact same timestamp (otherwise `timestamp_gt` alone would
    silently skip the overflow). This has no artificial ceiling — it is
    the pattern The Graph's own docs recommend for exactly this reason, and
    the same code handles both the initial backfill and every later
    refresh, with no `skip` involved anywhere.

    `max_pages` here is a genuine safety valve against a runaway loop (e.g.
    a query bug that never advances the cursor), not a silent truncation
    point like the old `skip`-based ceiling was: hitting it raises loudly
    instead of returning a partial, unflagged dataset.

    NOTE: field names match the ACTUAL deployed subgraph
    (api.studio.thegraph.com/query/1758817/zone-go/v0.0.1). The cursor
    query above uses graph-node's `or` where-combinator for the tiebreak
    branch — standard in current graph-node versions. VALIDATED: the team
    confirmed the `or:` combinator is accepted by the live deployed
    subgraph, tested with `lastId` as both String and Bytes — both pass.

    `since_timestamp`/`since_id`: resume the cursor from a previous call
    instead of always starting the backfill from zero. The cursor this
    function returns is just the last row of the DataFrame it hands back
    (already sorted ascending by timestamp, with `id` ties broken the same
    way the query does) — a caller doing incremental refreshes reads
    `df.iloc[-1][['timestamp', 'visit_id']]` from one call and passes it
    as `since_timestamp`/`since_id` on the next, and only pays for
    whatever's new since then instead of the whole history every time.
    Defaults (0, "") reproduce the old from-scratch behavior.

    STILL OPEN, per the team: this cursor's correctness assumes graph-node
    breaks same-timestamp ties in `id` order — true by construction (id is
    part of the ORDER BY specifically to make cursor pagination
    deterministic), and confirmed against a 3,500-row / 1,500-way-tie test
    scenario, but not yet confirmed against real indexed visits (the
    deployed subgraph has 0 so far — campaign 1 at Delancey is indexed,
    visits aren't, pending the contracts redeploy). Re-check this once real
    visits exist; if graph-node's tie-breaking ever differed, `id_gt`
    dropping true duplicates is the failure mode to watch for.
    """
    rows = []
    skipped = 0
    last_timestamp = since_timestamp
    last_id = since_id

    for page in range(max_pages):
        try:
            resp = requests.post(
                subgraph_url,
                json={
                    "query": _VISITS_QUERY,
                    "variables": {"first": page_size, "lastTimestamp": str(last_timestamp), "lastId": last_id},
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Subgraph request failed (page {page}, cursor {last_timestamp}/{last_id}): {exc}") from exc

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

        # Advance the cursor from the LAST row of this page regardless of
        # whether it was skipped above — a malformed geohash shouldn't
        # stall the cursor and cause the same bad row to be requested
        # forever.
        last_row = visits[-1]
        last_timestamp = int(last_row["timestamp"])
        last_id = last_row["id"]

        if len(visits) < page_size:
            break  # last page
    else:
        # The for/else fires only if we exhausted max_pages without a
        # short final page — i.e. the cursor never caught up. Raise loudly
        # instead of returning a silently partial dataset, per the same
        # principle as the old skip-based ceiling this replaces.
        raise RuntimeError(
            f"load_events_from_subgraph: hit max_pages={max_pages} without reaching the last "
            f"page (cursor stuck at timestamp={last_timestamp}, id={last_id}). This means either "
            f"there are more than {max_pages * page_size} visits indexed, or the cursor isn't "
            f"advancing correctly — investigate before trusting a partial result."
        )

    if skipped:
        print(f"load_events_from_subgraph: skipped {skipped} malformed visit(s) out of {skipped + len(rows)} fetched")

    df = pd.DataFrame(rows, columns=EVENT_SCHEMA)
    _validate_schema(df, require_label=False)
    return df

