"""
Canonical visit-event schema for ZoneGo's fraud pipeline.

The whole point of freezing this schema (Día 1 of the plan) is that
`build_features()` in train.py never has to change when the data source
changes. Today the only loader is the synthetic CSV; once Lucio's subgraph
(Día 4) is live, `load_events_from_subgraph()` becomes the real loader and
nothing downstream is touched, because both return the exact same columns.
"""

import pandas as pd

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


def _validate_schema(df: pd.DataFrame, require_label: bool = False) -> None:
    required = list(EVENT_SCHEMA) + ([LABEL_COLUMN] if require_label else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Events are missing required schema columns: {missing}")


def load_events_from_csv(path: str, require_label: bool = True) -> pd.DataFrame:
    """Adapter: synthetic/exported CSV -> canonical event schema.

    This is today's only data source (generate.py's output). It exists so
    the CSV's column names/order are an implementation detail of ONE loader,
    never something build_features() depends on directly.
    """
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    _validate_schema(df, require_label=require_label)
    cols = list(EVENT_SCHEMA) + ([LABEL_COLUMN] if require_label else [])
    return df[cols].copy()


def load_events_from_subgraph(subgraph_url: str, query: str = None) -> pd.DataFrame:
    """Adapter stub: subgraph (GraphQL) -> canonical event schema.

    Not wired to a live endpoint yet — that lands on Día 4 once Lucio
    deploys the subgraph and this can run a real GraphQL query against
    `Visit` entities. Kept here, with the same return contract as
    load_events_from_csv(), so that day only this function changes:
    build_features() and every model downstream stay exactly as they are.
    """
    raise NotImplementedError(
        "Subgraph querying is scheduled for Día 4 of the plan. When wired up, "
        "this must return a DataFrame with columns: " + ", ".join(EVENT_SCHEMA) +
        " (no `is_fraud` column — real events aren't labeled yet)."
    )
