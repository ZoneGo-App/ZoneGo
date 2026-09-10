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

def simulate_neighbor_collusion(businesses: pd.DataFrame, attack_start: datetime, hour_range: tuple = (10, 20)) -> pd.DataFrame:
    """8 wallets alternating between EXACTLY the two closest businesses to
    each other across the entire platform, every 20-40 minutes for 5 days --
    close enough and fast enough so that the implied velocity looks like
    walking between neighbors, not like impossible travel. `hour_range` is
    the time window of the day where each daily batch of alternations starts.
    """
    biz_a, biz_b = _nearest_pair(businesses)
    rng = np.random.default_rng(RANDOM_STATE + 2)
    wallets = [_new_wallet() for _ in range(8)]
    nullifiers = {w: _new_nullifier() for w in wallets}
    rows = []
    visit_n = 0
    lo, hi = hour_range
    for day in range(5):
        t = attack_start + timedelta(day, hours=int(rng.integers(lo, hi)))
        for _ in range(6):  # 6 alternations per day
            for w in wallets:
                biz = biz_a if (visit_n % 2 == 0) else biz_b
                visit_n += 1
                rows.append({
                    "visit_id": f"atk3_neighbor_{visit_n}",
                    "wallet": w,
                    "nullifier": nullifiers[w],
                    "business_id": biz["business_id"],
                    "business_type": biz["business_type"],
                    "lat": biz["lat"],
                    "lon": biz["lon"],
                    "timestamp": t,
                    "is_fraud": 1,
                    "fraud_type": "neighbor_collusion",
                })
                t = t + timedelta(minutes=int(rng.integers(20, 40)))
    return pd.DataFrame(rows)

def score_cold(attack_df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """Scenario "production today": exactly what infer.py does with a live
    wallet -- uses the FROZEN reference from the bundle, never recalculating
    it with what the attack brings.
    """
    df = add_sequential_features(attack_df)
    df = apply_aggregated_features(df, bundle["fitted_features"])
    X = df[bundle["feature_columns"]].fillna(0)
    df["fraud_score"] = bundle["model"].predict_proba(X)[:, 1]
    return df

def score_warm(background_df: pd.DataFrame, attack_df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """Scenario "refreshed reference": simulates a periodic refresh of
    fit_aggregated_features() that DOES include the attack traffic, but
    without retraining the classifier (gb remains the same already-trained
    model). Measures the real power of graph features when they have
    visibility into the attack graph.
    """
    combined = pd.concat([background_df, attack_df], ignore_index=True, sort=False)
    combined = add_sequential_features(combined)
    refreshed_fitted = fit_aggregated_features(combined)

    attack_only = combined[combined["fraud_type"].isin(attack_df["fraud_type"].unique())].copy()
    attack_only = apply_aggregated_features(attack_only, refreshed_fitted)
    X = attack_only[bundle["feature_columns"]].fillna(0)
    attack_only["fraud_score"] = bundle["model"].predict_proba(X)[:, 1]
    return attack_only

def detection_rate(scored_df: pd.DataFrame, threshold: float) -> float:
    if len(scored_df) == 0:
        return 0.0
    return float((scored_df["fraud_score"] >= threshold).mean())


def run():
    background = load_background()
    businesses = pick_businesses(background)
    bundle = joblib.load(BUNDLE_PATH)
    threshold_f1 = bundle["threshold_info"]["f1_point"]["threshold"]
    threshold_hr = bundle["threshold_info"]["high_recall_point"]["threshold"]
    business_mode = bundle["fitted_features"]["business_mode"]

    attack_start = background["timestamp"].max() + timedelta(days=1)

    # "Naive": the attacker doesn't think about the business schedule.
    naive_attacks = {
        "Farm of 30 verified wallets": simulate_farm_30_verified_wallets(businesses, attack_start),
        "Self-visiting business": simulate_self_visiting_business(businesses, attack_start),
        "Neighbor collusion between 2 businesses": simulate_neighbor_collusion(businesses, attack_start),
    }

    # "Adaptive": the same attack, but timed to the REAL peak hour of the
    # target business (taken from the already frozen reference) -- what any
    # minimally careful attacker would do to avoid giving away the most obvious signal (hour_deviation).
    farm_target_hour = int(business_mode.get(
        businesses.sample(1, random_state=RANDOM_STATE).iloc[0]["business_id"], 12
    ))
    self_visit_target = businesses.sample(1, random_state=RANDOM_STATE + 1).iloc[0]
    self_visit_hour = int(business_mode.get(self_visit_target["business_id"], 12))
    biz_a, biz_b = _nearest_pair(businesses)
    neighbor_hour = int(business_mode.get(biz_a["business_id"], 12))

    adaptive_attacks = {
        "Farm of 30 verified wallets": simulate_farm_30_verified_wallets(
            businesses, attack_start, target_hour=farm_target_hour
        ),
        "Self-visiting business": simulate_self_visiting_business(
            businesses, attack_start, target_hour_range=(max(self_visit_hour - 1, 0), self_visit_hour + 2)
        ),
        "Neighbor collusion between 2 businesses": simulate_neighbor_collusion(
            businesses, attack_start, hour_range=(max(neighbor_hour - 1, 0), neighbor_hour + 2)
        ),
    }

    rows_summary = []
    for name in naive_attacks:
        naive_df = naive_attacks[name]
        adaptive_df = adaptive_attacks[name]

        cold_naive = score_cold(naive_df, bundle)
        warm_naive = score_warm(background, naive_df, bundle)
        cold_adaptive = score_cold(adaptive_df, bundle)
        warm_adaptive = score_warm(background, adaptive_df, bundle)

        rows_summary.append({
            "Attack": name,
            "N simulated visits": len(naive_df),
            "Detection TODAY — naive attacker": detection_rate(cold_naive, threshold_f1),
            "Detection TODAY — attacker avoiding weird hours": detection_rate(cold_adaptive, threshold_f1),
            "Refreshed detection — naive": detection_rate(warm_naive, threshold_f1),
            "Refreshed detection — evades hours": detection_rate(warm_adaptive, threshold_f1),
            "Average score TODAY (naive)": cold_naive["fraud_score"].mean(),
            "Average score TODAY (avoids hours)": cold_adaptive["fraud_score"].mean(),
        })

    df_summary = pd.DataFrame(rows_summary)
    write_report(df_summary, threshold_f1, threshold_hr)
    return df_summary


def write_report(df_summary: pd.DataFrame, threshold_f1: float, threshold_hr: float, path: str = REPORT_PATH):
    def pct(x):
        return f"{x:.0%}"

    rows_md = "\n".join(
        f"| {r['Attack']} | {r['N simulated visits']} | {pct(r['Detection TODAY — naive attacker'])} | "
        f"{pct(r['Detection TODAY — attacker avoiding weird hours'])} |"
        for _, r in df_summary.iterrows()
    )

    rows_warm_md = "\n".join(
        f"| {r['Attack']} | {pct(r['Refreshed detection — naive'])} | {pct(r['Refreshed detection — evades hours'])} |"
        for _, r in df_summary.iterrows()
    )

    content = f"""# Attack Simulation — material for the jury

Generated by `attack_simulation.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Three attacks that **do not exist in `generate.py`** (the model never saw them
during training), simulated against the fully trained system already in place
(`fraud_model.joblib`) and annotated over real platform businesses.
Each was designed to intentionally evade a different defense and test
another — see docstrings in `attack_simulation.py` for the reasoning behind each.

Each attack is run in two versions, because a single "detection" number without this is misleading:

- **Naive**: the attacker does not think about the target business's schedule.
- **Avoids weird hours**: the same attack, but timed to the real peak hour
  of the business — what any minimally careful attacker would do to avoid
  giving away the most obvious and readable signal (`hour_deviation`).

Threshold used (from `train.py`, precision-recall curve — see main README.md,
optimal F1 point): {threshold_f1:.4f}.

## Detection rate — production as-is today

| Attack | Simulated visits | Detection (naive) | Detection (avoids hours) |
|---|---|---|---|
{rows_md}

## With refreshed graph reference (without retraining the classifier)

Same model, recalculating `fit_aggregated_features()` to include the attack
traffic before scoring it — as would happen if the team refreshes the graph
reference periodically instead of calculating it once upon training:

| Attack | Detection (naive) | Detection (evades hours) |
|---|---|---|
{rows_warm_md}

## Honest read for the jury

**The number that matters is the "avoids hours" column, not the "naive" one.**
Running this found that the high detection of the 30-wallet farm in the naive scenario (left column) doesn't come from the co-visit pattern designed to catch it — it comes from the fact that, by chance, the chosen attack time didn't match the historical peak hour of that business (`hour_deviation` large). As soon as the attack is timed to the real peak hour of the target business (right column), detection drops against real platform businesses:

- **Farm of 30 verified wallets**: each wallet has its own nullifier (30 distinct
  verifications, not a reused one), so `sybil_score` cannot see it by design.
  Without the schedule accident, detection of this specific attack depends on
  `covisit_partners` having visibility into the attack graph — and today, with
  the reference frozen at training time, brand new wallets do not appear there yet.
- **Self-visiting business**: with only 2 wallets, almost all possible signal comes
  from `business_entropy` (visits only one business → entropy close to 0). Today,
  that signal is hidden from new wallets by an intentional safeguard in
  `features.py` (Observation #6): a brand new wallet without history is assigned
  the MEDIAN entropy of the dataset rather than 0, precisely to avoid punishing
  a legitimate new client for lacking history yet. That same safeguard delays seeing
  the real signal of a new wallet that IS fraud — it's a conscious trade-off,
  not a bug, but worth disclosing to the jury.
- **Neighbor collusion between 2 businesses**: `implied_velocity` doesn't see it
  by design (the two businesses are meters apart). Of the three, it is the attack
  with the lowest detection in both scenarios — entropy is split across 2 businesses
  instead of 1, a weaker signal than pure self-visiting.

**Why the classifier doesn't better leverage graph features even when they have fresh data (column "refreshed reference")**: in training data (`generate.py`), the only pattern with many new wallets at a single business is `co_visit`, where the same 5 wallets repeat hundreds of times (not 30 single-use wallets each). The classifier never saw, during training, the exact pattern "many single-use wallets, no shared nullifier, co-visiting once" — which is why it doesn't weight it as strongly as it should, even though the feature (`covisit_partners`) registers the correct number once it has graph visibility.

**Operational recommendation, in two parts**:
1. Periodically refresh `fit_aggregated_features()` (e.g., every 24-48h) over
   everything indexed up to that point, rather than just once at training --
   it's cheap (doesn't retrain the classifier) and gives graph features
   visibility into attacks happening after training.
2. Once the team confirms real cases (or more realistically simulated ones) of
   new wallet farms and self-visiting, add them as labeled examples and
   retrain -- step 1 gives the model the right data, but the model also needs
   examples of THIS specific pattern to learn to weight it with the force it deserves.

## How attacks were generated

- Uses `data/visits.csv` (the output of `generate.py`) as "everything indexed
  so far", and attacks target REAL businesses from that file, never invented ones.
- All wallets in the three attacks are new (do not reuse historical wallets),
  because it's the hardest case for the system — and the most realistic for an
  attacker who doesn't want to reuse a known wallet.
- The "TODAY" scenario uses `bundle['fitted_features']` exactly as saved by
  `train.py` — the exact code path used by `infer.py`/`api/routers/score.py`
  in production, not a simplified version.
- The "avoids hours" scenario uses the real peak hour (`modal_hour`) of the
  target business, taken from that same frozen reference, so that the comparison
  is over the SAME business and the SAME attack, changing only the timing.
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Attack report saved to {path}")


if __name__ == "__main__":
    df_summary = run()
    pd.set_option("display.width", 140)
    print(df_summary.to_string(index=False))