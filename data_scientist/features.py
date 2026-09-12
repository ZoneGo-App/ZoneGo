"""
Shared feature-computation logic for BOTH training (train.py) and live
inference (infer.py).

This file exists to fix Observation #5: compute_graph_reference(df_train)
was only ever called inside train.py's build_features(), and its output
was never saved. At inference time there is no df_train, so the three
graph features had nothing to compute from -- the model couldn't actually
be served even with a saved joblib.

The fix: split "fit the aggregates" from "apply the aggregates" into
importable functions. train.py calls fit once on the training split and
persists the result (see train.py's MODEL_BUNDLE_PATH); infer.py loads
that same persisted bundle and calls apply() on live wallets. Same code,
same fitted numbers, both times -- nothing about inference re-derives
anything from scratch.

ADDED: `wallet_farm_signal`, combining World's Sybil signal
(`sybil_score`, from graph_features.py) with the subgraph co-visit signal
(`covisit_partners`). Nothing in train.py or infer.py needed to change for
this to reach the model -- both files import FEATURES_ALL from here, so
adding one name to that list is enough for it to flow through
build_features(), the saved joblib bundle, and live scoring alike.
"""

import numpy as np
import pandas as pd

from graph_features import compute_graph_reference, apply_graph_features, GRAPH_FEATURES

FEATURES_V1 = ['previous_time', 'implied_velocity', 'hour_deviation', 'covisit_degree']
# GRAPH_FEATURES now includes sybil_score (graph_features.py); wallet_farm_signal
# is the explicit interaction between it and covisit_partners, computed below.
FEATURES_ALL = FEATURES_V1 + GRAPH_FEATURES + ['wallet_farm_signal']


def add_sequential_features(df: pd.DataFrame) -> pd.DataFrame:
    """previous_time / implied_velocity: depend only on each entity's own
    past (grouped by nullifier / wallet respectively), never on a
    dataset-wide aggregate. Safe to compute on ANY dataframe -- train,
    test, or a live batch of events at inference time -- without a fitted
    reference from anywhere else.
    """
    df = df.copy()
    df['hour'] = df['timestamp'].dt.hour
    df['hour_window'] = df['timestamp'].dt.floor('h')
    lat_correction = np.cos(np.radians(df['lat'].mean())) if len(df) else 1.0

    by_nullifier = df.sort_values(by=['nullifier', 'timestamp'])
    previous_time = (
        by_nullifier.groupby('nullifier')['timestamp']
        .diff().dt.total_seconds().fillna(999999)
    )
    df['previous_time'] = previous_time.reindex(df.index)

    by_wallet = df.sort_values(by=['wallet', 'timestamp'])

    lat_prev = by_wallet.groupby('wallet')['lat'].shift(1)
    lon_prev = by_wallet.groupby('wallet')['lon'].shift(1)
    time_prev = by_wallet.groupby('wallet')['timestamp'].shift(1)
    dist_prev = np.sqrt((by_wallet['lat'] - lat_prev) ** 2 + ((by_wallet['lon'] - lon_prev) * lat_correction) ** 2)
    seconds_prev = (by_wallet['timestamp'] - time_prev).dt.total_seconds()
    velocity_prev = dist_prev / (seconds_prev.fillna(999999) + 1)

    lat_next = by_wallet.groupby('wallet')['lat'].shift(-1)
    lon_next = by_wallet.groupby('wallet')['lon'].shift(-1)
    time_next = by_wallet.groupby('wallet')['timestamp'].shift(-1)
    dist_next = np.sqrt((by_wallet['lat'] - lat_next) ** 2 + ((by_wallet['lon'] - lon_next) * lat_correction) ** 2)
    seconds_next = (time_next - by_wallet['timestamp']).dt.total_seconds()
    velocity_next = dist_next / (seconds_next.fillna(999999) + 1)

    implied_velocity = pd.concat([velocity_prev, velocity_next], axis=1).max(axis=1).fillna(0)
    df['implied_velocity'] = implied_velocity.reindex(df.index)
    return df


def fit_aggregated_features(train_df: pd.DataFrame) -> dict:
    """Fits every aggregate that must be computed ONLY on training data:
    modal hour per business, co-visit degree per business/hour window, and
    the four graph-reference features (including sybil_score). Returns a
    plain dict that gets persisted alongside the trained model (train.py's
    MODEL_BUNDLE_PATH), so infer.py never has to re-fit anything from live
    data.
    """
    global_mode_hour = train_df['hour'].mode()[0]
    business_mode = (
        train_df.groupby('business_id')['hour']
        .agg(lambda x: x.mode()[0] if not x.empty else global_mode_hour)
        .rename('modal_hour')
    )
    covisits_train = (
        train_df.groupby(['business_id', 'hour_window'])['wallet']
        .nunique()
        .rename('covisit_degree')
        .reset_index()
    )
    graph_reference = compute_graph_reference(train_df)

    return {
        'global_mode_hour': global_mode_hour,
        'business_mode': business_mode,
        'covisits_train': covisits_train,
        'graph_reference': graph_reference,
    }


def apply_aggregated_features(df: pd.DataFrame, fitted: dict) -> pd.DataFrame:
    """Applies a previously-fitted bundle (from fit_aggregated_features) to
    ANY dataframe: the test split during training, or a live wallet's
    events during inference. Same function, same fitted numbers, every
    time -- this is what makes the model servable at all.
    """
    df = df.merge(fitted['business_mode'], on='business_id', how='left')
    df['modal_hour'] = df['modal_hour'].fillna(fitted['global_mode_hour'])
    df['hour_deviation'] = np.abs(df['hour'] - df['modal_hour'])

    df = df.merge(fitted['covisits_train'], on=['business_id', 'hour_window'], how='left')
    df['covisit_degree'] = df['covisit_degree'].fillna(1)

    df = apply_graph_features(df, fitted['graph_reference'])

    # FIX (Observation #6): apply_graph_features() defaults an unseen
    # wallet's business_entropy to 0 -- but entropy 0 is ALSO the score of
    # the single most suspicious wallet (always visits the exact same
    # business). A brand-new, legitimate visitor would enter the model
    # wearing the fraud signature that feature exists to catch.
    #
    # "No history yet" is not evidence of fraud, so a never-seen wallet
    # gets the dataset's MEDIAN entropy instead -- a neutral value, not the
    # most-suspicious one. This is a stopgap, not the cleanest possible
    # fix: a separate boolean "has_history" flag (as the review suggested)
    # would let the model learn its own weighting for "unknown" instead of
    # this hardcoded substitution -- worth doing if entropy's feature
    # importance turns out to matter more later.
    known_wallets = fitted['graph_reference']['business_entropy'].index
    neutral_entropy = (
        fitted['graph_reference']['business_entropy'].median()
        if len(known_wallets) else 0.0
    )
    df.loc[~df['wallet'].isin(known_wallets), 'business_entropy'] = neutral_entropy

    # Combine World's Sybil signal with the subgraph co-visit signal
    # ("Combinarla con los rasgos de co-visita del subgraph"). Each alone
    # can have an innocent explanation on its own -- a shared nullifier
    # could just be a device/account-recovery edge case, and a co-visit
    # cluster could be a family or a line at a popular register. A wallet
    # that is BOTH sharing its nullifier with other wallets AND showing up
    # in lockstep with them at the same business/hour is the actual
    # wallet-farm shape (generate.py's Pattern 2 co_visit and Pattern 4
    # repeated_nullifier are meant to be caught together, not separately).
    #
    # GradientBoostingClassifier already learns interactions between raw
    # features on its own, so this explicit product isn't strictly
    # necessary for the model -- it's added because it gives one
    # human-readable "how much does this look like a farm" number for the
    # README's top-features table and any future ops dashboard, without
    # removing the two raw signals (still available separately to the
    # model as sybil_score / covisit_partners).
    df['wallet_farm_signal'] = df['sybil_score'] * (1 + df['covisit_partners'])

    return df

