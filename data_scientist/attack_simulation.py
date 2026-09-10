"""
attack_simulation.py

Simulates three attacks that do NOT exist in generate.py (meaning the model
never saw them during training) and measures how well the FULL SYSTEM
already trained (fraud_model.joblib) detects them: the exact same bundle used
by infer.py / api/routers/score.py in production today.

Why these three and not something else: each is specifically designed to
test a different defense, and to evade another:

1. Farm of 30 VERIFIED wallets
   Each wallet has its OWN unique nullifier (30 real human verifications,
   not 30 wallets reusing a single identity). This purposely evades
   sybil_score (which only looks at nullifier reuse) -- it is exactly the
   attack that World ID's "one person = one vote" does NOT solve on its
   own. The only thing that can see it is the co-visit graph: 30 new wallets,
   same business, same time window.

2. Self-visiting business
   Few wallets (here 2) that visit ONLY their own business, many times.
   An attack designed for business_entropy, which exists specifically for
   this (entropy ~0 = always the same place).

3. Collusion between two neighboring merchants
   A group of wallets alternates between EXACTLY two geographically close
   businesses. Being close, the distance/time between consecutive visits
   does NOT look like an "impossible travel" -- purposely evading
   implied_velocity. What can see it: business_entropy (distributed across
   2 instead of 1) and covisit_partners.

Each attack is measured in TWO scenarios, because the current architecture
makes the actual response different depending on which one applies:

- "PRODUCTION TODAY" (cold): the trained bundle has its graph_reference
  (covisit_partners, business_entropy, sybil_score) and its covisits_train
  FROZEN from training. Wallets and time windows that never existed at that
  moment receive the default neutral value, even if they are behaving
  exactly like the pattern the feature looks for. This is what would
  actually happen today if the attack occurs after training -- it is the
  real question from the jury.
- "WITH REFRESHED REFERENCE" (warm): if the team recalculates
  fit_aggregated_features() including the attack traffic (e.g., a periodic
  refresh of the graph reference over everything indexed, WITHOUT retraining
  the classifier), does the already trained model see it? This measures how
  much power graph features have when they DO have visibility into the
  attack graph, and is the technical justification for the operational
  recommendation at the end of this script.
"""


import os
import secrets
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

from features import FEATURES_ALL, add_sequential_features, fit_aggregated_features, apply_aggregated_features

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "visits.csv")
BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.joblib")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "ATTACK_SIMULATION_REPORT.md")

RANDOM_STATE = 7  # own seed, distinct from generate.py/train.py

def _new_wallet():
    return f"0x{secrets.token_hex(20)}"


def _new_nullifier():
    return f"null_{secrets.token_hex(8)}"


def load_background():
    """Everything indexed so far -- the background against which each
    attack occurs. Uses data/visits.csv (the output of generate.py) as a
    proxy for "all history already seen by the system".
    """
    df = pd.read_csv(DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def pick_businesses(background_df: pd.DataFrame) -> pd.DataFrame:
    """A real business by business_id, with its location -- attacks target
    businesses that ALREADY exist on the platform, not invented businesses,
    because that is how a real attack would happen.
    """
    return (
        background_df[["business_id", "business_type", "lat", "lon"]]
        .drop_duplicates(subset="business_id")
        .reset_index(drop=True)
    )


def _nearest_pair(businesses: pd.DataFrame) -> tuple:
    """The CLOSEST pair of businesses to each other -- the "neighbors" of
    attack 3. Euclidean distance in degrees, same as generate.py.
    """
    best = None
    for i in range(len(businesses)):
        for j in range(i + 1, len(businesses)):
            a, b = businesses.iloc[i], businesses.iloc[j]
            d = np.sqrt((a["lat"] - b["lat"]) ** 2 + (a["lon"] - b["lon"]) ** 2)
            if best is None or d < best[0]:
                best = (d, a, b)
    _, a, b = best
    return a, b


def simulate_farm_30_verified_wallets(businesses: pd.DataFrame, attack_start: datetime, target_hour: int = None) -> pd.DataFrame:
    """30 NEW wallets, each with its OWN nullifier (30 real/distinct
    verifications), all visiting the SAME business within a 90-minute
    window. None reuse a nullifier with another -- on purpose, to evade
    sybil_score.

    `target_hour`, if provided, forces the attack start hour (for the
    "intelligent attacker" scenario that purposely avoids the weird hour).
    """
    target = businesses.sample(1, random_state=RANDOM_STATE).iloc[0]
    base = attack_start if target_hour is None else attack_start.replace(hour=target_hour, minute=0)
    rows = []
    for i in range(30):
        w = _new_wallet()
        n = _new_nullifier()  # unique per wallet -- truly "verified"
        t = base + timedelta(minutes=int(np.random.default_rng(RANDOM_STATE + i).integers(0, 90)))
        rows.append({
            "visit_id": f"atk1_farm30_{i}",
            "wallet": w,
            "nullifier": n,
            "business_id": target["business_id"],
            "business_type": target["business_type"],
            "lat": target["lat"],
            "lon": target["lon"],
            "timestamp": t,
            "is_fraud": 1,
            "fraud_type": "farm_30_verified_wallets",
        })
    return pd.DataFrame(rows)

def simulate_self_visiting_business(businesses: pd.DataFrame, attack_start: datetime, target_hour_range: tuple = (10, 19)) -> pd.DataFrame:
    """2 new wallets (the merchant and/or a close accomplice) that visit
    ONLY their own business, 25 times each, spread over 10 days, during normal
    business hours (so that hour_deviation is NOT what gives them away -- the
    point is to isolate how well business_entropy catches them alone).
    `target_hour_range` is the range of hours of the day when visits occur.
    """
    target = businesses.sample(1, random_state=RANDOM_STATE + 1).iloc[0]
    rng = np.random.default_rng(RANDOM_STATE + 1)
    wallets = [_new_wallet(), _new_wallet()]
    nullifiers = {w: _new_nullifier() for w in wallets}
    rows = []
    visit_n = 0
    lo, hi = target_hour_range
    for day in range(10):
        for w in wallets:
            visit_n += 1
            t = attack_start + timedelta(days=day, hours=int(rng.integers(lo, hi)), minutes=int(rng.integers(0, 60)))
            rows.append({
                "visit_id": f"atk2_selfvisit_{visit_n}",
                "wallet": w,
                "nullifier": nullifiers[w],
                "business_id": target["business_id"],
                "business_type": target["business_type"],
                "lat": target["lat"],
                "lon": target["lon"],
                "timestamp": t,
                "is_fraud": 1,
                "fraud_type": "self_visiting_business",
            })
    return pd.DataFrame(rows)
