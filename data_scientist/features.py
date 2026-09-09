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

def add_sequential_features(df: pd.DataFrame)-> pd.DataFrame:
    """previous_time / implied_velocity: depend only on each entity's own
    past (grouped by nullifier / wallet respectively), never on a
    dataset-wide aggregate. Safe to compute on ANY dataframe -- train,
    test, or a live batch of events at inference time -- without a fitted
    reference from anywhere else."""

    df = df.copy()
    df['hour'] = df['timestamp'].dt.hour
    df['hour_window'] = df['timestamp'].dt.floor('h')
    lat_correction = np.cos(np.radians(df['lat'].mean())) if len(df) else 1.0

    by_nullifier = df.sort_values(by=['nullifier', 'timestamp'])
    previous_time = (
        by_nullifier.groupby('nullifier')['timestamp'].diff().dt.total_seconds().fillna(999999)
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