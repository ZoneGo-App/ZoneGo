"""
Graph-only features (Day 4 of the plan).

Each of these needs the FULL indexed history across MANY wallets and
businesses -- not just one wallet's own sequence -- which is exactly why
they didn't exist before the subgraph became the source of truth. None of
them are computable from a single row or a single wallet's local history;
they require traversing the visit graph.

Same leak-safe discipline as the aggregated features in train.py: every
function here is split into a `compute_*_reference()` step (run ONLY on the
training rows) and an `apply_*()` step (maps that reference onto any other
subset, train or test), so the test set never leaks into the numbers a
training row sees.

ADDED: `sybil_score` (World's Sybil signal).

World ID's guarantee is that `nullifier` is the same for the same real
person no matter how many wallets they claim from -- it's literally
"how many times that face was recognized on the platform." We don't need
a separate call to a World API to get this: the nullifier is already in
EVENT_SCHEMA (events.py) for both the CSV and the live subgraph loader, so
the wallet-farm signal is just "how many OTHER wallets share this same
nullifier" -- a graph aggregate exactly like the other three, and exactly
what generate.py's `repeated_nullifier` fraud pattern (Pattern 4) creates.
That pattern existed in the training data with NO feature that could see
it until now -- this closes that gap. If "Sybil Score" is meant to come
from an external World endpoint instead of being derived from our own
event history, only `_nullifier_reuse_reference` below needs to change;
everything downstream (features.py, train.py, infer.py) stays the same
because it only depends on there being a `sybil_score` column.
"""

import numpy as np
import pandas as pd

GRAPH_FEATURES = ["covisit_partners", "business_entropy", "temporal_concentration", "sybil_score"]


def _covisit_partners_reference(df: pd.DataFrame) -> pd.Series:
    """For each wallet: how many DISTINCT other wallets has it been recorded
    at the same business, in the same hour window, with? A wallet with many
    distinct co-visit partners is exactly the shape of a coordinated
    co-visit ring -- but detecting it needs the whole graph of who-was-where
    -when, not one wallet's own rows.
    """
    grouped = df.groupby(["business_id", "hour_window"])["wallet"].apply(set)

    partners = {}
    for wallets_in_slot in grouped:
        if len(wallets_in_slot) < 2:
            continue
        for w in wallets_in_slot:
            partners.setdefault(w, set()).update(wallets_in_slot - {w})

    if not partners:
        return pd.Series(dtype=float, name="covisit_partners")

    return pd.Series({w: len(p) for w, p in partners.items()}, name="covisit_partners")


def _business_entropy_reference(df: pd.DataFrame) -> pd.Series:
    """Shannon entropy of the distribution of businesses each wallet has
    visited. A wallet that always shows up at the SAME one or two
    businesses (co-visit / Sybil funnel patterns) has low entropy; a
    natural visitor with varied habits has higher entropy. Requires the
    wallet's whole visit history, indexed across every business.
    """
    counts = df.groupby(["wallet", "business_id"]).size().rename("n").reset_index()
    totals = counts.groupby("wallet")["n"].transform("sum")
    probs = counts["n"] / totals
    counts["plogp"] = -probs * np.log2(probs)
    entropy = counts.groupby("wallet")["plogp"].sum().rename("business_entropy")
    return entropy


def _temporal_concentration_reference(df: pd.DataFrame) -> pd.Series:
    """For each business (standing in for its campaign): what share of ALL
    its visits fall inside its single busiest hour window? A burst attack
    (co-visit, Sybil) concentrates a business's traffic into one narrow
    window -- but seeing that requires every visit to that business across
    the whole dataset, not just the current row.
    """
    per_slot = df.groupby(["business_id", "hour_window"]).size().rename("n").reset_index()
    totals = per_slot.groupby("business_id")["n"].transform("sum")
    per_slot["share"] = per_slot["n"] / totals
    concentration = per_slot.groupby("business_id")["share"].max().rename("temporal_concentration")
    return concentration


def _nullifier_reuse_reference(df: pd.DataFrame) -> pd.Series:
    """World's Sybil signal: for each wallet, how many OTHER distinct
    wallets share its exact same `nullifier` (the same real-world "face"
    World ID recognized)? A legitimate wallet's nullifier belongs to it
    alone (reuse = 0). A wallet-farm attack is many fresh wallets funneling
    claims under ONE shared nullifier -- generate.py's `repeated_nullifier`
    pattern (Pattern 4) is exactly this, and it's a graph fact: you can
    only see it by looking at every wallet that ever used a given
    nullifier, not at one wallet's own rows.
    """
    grouped = df.groupby("nullifier")["wallet"].apply(lambda s: set(s))

    reuse = {}
    for wallets_sharing in grouped:
        if len(wallets_sharing) < 2:
            continue
        for w in wallets_sharing:
            reuse[w] = len(wallets_sharing) - 1  # count of OTHER wallets behind the same face

    if not reuse:
        return pd.Series(dtype=float, name="sybil_score")

    return pd.Series(reuse, name="sybil_score")


def compute_graph_reference(train_df: pd.DataFrame) -> dict:
    """Computes all four graph aggregates from a REFERENCE set (the
    training split). Call this ONCE on df_train, then apply_graph_features()
    on both df_train and df_test with the same reference -- never recompute
    the reference from df_test, or test-set structure leaks into training.
    """
    return {
        "covisit_partners": _covisit_partners_reference(train_df),
        "business_entropy": _business_entropy_reference(train_df),
        "temporal_concentration": _temporal_concentration_reference(train_df),
        "sybil_score": _nullifier_reuse_reference(train_df),
    }


def apply_graph_features(df: pd.DataFrame, reference: dict) -> pd.DataFrame:
    """Maps a precomputed reference onto df (train or test). Rows whose
    wallet/business never appeared in the reference set get the neutral
    default: 0 partners, 0 entropy (a single unseen visit has no
    distribution to measure), 0 concentration, 0 sybil_score.

    Note the asymmetry with `business_entropy` (see features.py's
    apply_aggregated_features, Observation #6 fix): there, 0 is the score
    of the MOST suspicious wallet, so an unseen wallet can't be defaulted
    to 0 safely. `sybil_score` has the opposite shape -- 0 IS the neutral,
    "nothing suspicious detected" value (no nullifier reuse seen), so
    defaulting an unseen wallet to 0 here is safe and needs no equivalent
    stopgap.
    """
    df = df.copy()
    df["covisit_partners"] = df["wallet"].map(reference["covisit_partners"]).fillna(0)
    df["business_entropy"] = df["wallet"].map(reference["business_entropy"]).fillna(0)
    df["temporal_concentration"] = df["business_id"].map(reference["temporal_concentration"]).fillna(0)
    df["sybil_score"] = df["wallet"].map(reference["sybil_score"]).fillna(0)
    return df

