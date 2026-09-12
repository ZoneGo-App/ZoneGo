import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import secrets
from itertools import combinations

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "visits.csv")

BUSINESS_TYPES = [
    "bodega", "deli", "laundromat", "barbershop",
    "pizzeria", "coffee_shop", "nail_salon", "hardware_store",
]


def data_generate(n_businesses=50, n_neighbors=500, n_visits=20000, seed=42):
    np.random.seed(seed)

    # 1. BUSINESSES — Lower East Side / East Village, Manhattan.
    # Sigma of 0.008 deg (~900 m) instead of Lima's 0.015: a Manhattan
    # neighborhood is denser, and 900 m is the real scale of walking to shop.
    lat_center, lon_center = 40.7220, -73.9870
    businesses = pd.DataFrame({
        'business_id': [f"business_{i:03d}" for i in range(n_businesses)],
        'business_type': np.random.choice(BUSINESS_TYPES, n_businesses),
        'lat': lat_center + np.random.normal(0, 0.008, n_businesses),
        'lon': lon_center + np.random.normal(0, 0.008, n_businesses),
        'open': np.random.randint(7, 10, n_businesses),
        'close': np.random.randint(20, 23, n_businesses),
    })

    # Pre-compute the farthest-apart pair of businesses once. It is reused by
    # the impossible-travel pattern below (same idea as pattern 2's fixed
    # "focus" business: a real, stable anchor rather than a random shift).
    pairs = list(combinations(businesses.index, 2))
    pair_distances = [
        np.sqrt((businesses.loc[a, 'lat'] - businesses.loc[b, 'lat']) ** 2 +
                (businesses.loc[a, 'lon'] - businesses.loc[b, 'lon']) ** 2)
        for a, b in pairs
    ]
    far_a_idx, far_b_idx = pairs[int(np.argmax(pair_distances))]
    business_far_a = businesses.loc[far_a_idx]
    business_far_b = businesses.loc[far_b_idx]

    # 2. NEIGHBORS (Wallets) — ONE STABLE NULLIFIER PER WALLET.
    # This is what World ID actually guarantees in the real system: a human
    # keeps the same nullifier across visits. A random nullifier per visit
    # (the previous version) made `previous_time` a dead, near-constant
    # feature, because almost no two rows ever shared a nullifier.
    wallet_list = [f"0x{secrets.token_hex(20)}" for _ in range(n_neighbors)]
    nullifier_of = {w: f"null_{secrets.token_hex(8)}" for w in wallet_list}

    # Precalculate fraud pattern sizes. Patterns 1, 2 and 4 now ADD new rows
    # (impossible travel needs two brand-new visit rows per incident); only
    # pattern 3 flips existing legitimate rows in place. So the base volume
    # has to leave room for three patterns, not two, to land on n_visits exactly.
    n_fraud_target = int(n_visits * 0.08)
    n_per_pattern = n_fraud_target // 4
    n_base_visit = n_visits - (3 * n_per_pattern)

    # 3. GENERATE BASE VISITS (Legitimate)
    date_base = [datetime(2026, 9, 1) + timedelta(days=np.random.randint(0, 5)) for _ in range(n_base_visit)]

    visit = []
    for i in range(n_base_visit):
        selected_wallet = np.random.choice(wallet_list)
        trade = businesses.sample(1).iloc[0]

        hour = np.random.randint(trade['open'], trade['close'])
        minute = np.random.randint(0, 60)
        time = date_base[i].replace(hour=hour, minute=minute)

        visit.append({
            'visit_id': f"v_{i:06d}",
            'wallet': selected_wallet,
            'business_id': trade['business_id'],
            'business_type': trade['business_type'],
            'lat': trade['lat'],
            'lon': trade['lon'],
            'timestamp': time,
            'nullifier': nullifier_of[selected_wallet],
            'is_fraud': 0,
            'fraud_type': 'normal',
        })

    df = pd.DataFrame(visit)

    # 4. INJECT FRAUD PATTERNS

    # --- Pattern 1: Impossible travel — moves the VISITOR, not the business ---
    # One wallet is recorded at the two farthest-apart REAL businesses in the
    # neighborhood, three minutes apart. That is what implied_velocity is
    # supposed to catch: a person, not a teleporting storefront.
    n_incidents_p1 = max(n_per_pattern // 2, 1)
    for i in range(n_incidents_p1):
        wallet = np.random.choice(wallet_list)
        base_day = datetime(2026, 9, 1) + timedelta(days=int(np.random.randint(0, 5)))
        base_time = base_day.replace(hour=int(np.random.randint(9, 20)), minute=int(np.random.randint(0, 60)))

        for suffix, biz, delta_min in [('a', business_far_a, 0), ('b', business_far_b, 3)]:
            new_idx = len(df)
            df.loc[new_idx] = {
                'visit_id': f"v_fraud_p1_{i}_{suffix}",
                'wallet': wallet,
                'business_id': biz['business_id'],
                'business_type': biz['business_type'],
                'lat': biz['lat'],
                'lon': biz['lon'],
                'timestamp': base_time + timedelta(minutes=delta_min),
                'nullifier': nullifier_of[wallet],
                'is_fraud': 1,
                'fraud_type': 'impossible_travel',
            }

    # --- Pattern 2: Systematic co-visit ---
    # Several wallets that always show up together at the same business at
    # the same time — unchanged in concept, now carrying each wallet's own
    # stable nullifier instead of a random one.
    group_malicious = np.random.choice(wallet_list, 5, replace=False)
    trade_foco = businesses.sample(1).iloc[0]
    time_foco = datetime(2026, 9, 3, 15, 0, 0)

    for i in range(n_per_pattern):
        bil = group_malicious[i % len(group_malicious)]
        new_idx = len(df)
        df.loc[new_idx] = {
            'visit_id': f"v_fraud_p2_{i}",
            'wallet': bil,
            'business_id': trade_foco['business_id'],
            'business_type': trade_foco['business_type'],
            'lat': trade_foco['lat'],
            'lon': trade_foco['lon'],
            'timestamp': time_foco + timedelta(seconds=i * 5),
            'nullifier': nullifier_of[bil],
            'is_fraud': 1,
            'fraud_type': 'co_visit',
        }

    # --- Pattern 3: Out-of-hours burst (unchanged: flips existing rows) ---
    # FIX #4: only pick from rows that are still legitimate. Sampling from
    # df.index (all rows) could re-label an impossible_travel or co_visit
    # row as out_of_hours, silently destroying the pattern it represented.
    idx_p3 = np.random.choice(df[df['is_fraud'] == 0].index, n_per_pattern, replace=False)
    for idx in idx_p3:
        df.loc[idx, 'is_fraud'] = 1
        df.loc[idx, 'fraud_type'] = 'out_of_hours'
        t_current = df.loc[idx, 'timestamp']
        df.loc[idx, 'timestamp'] = t_current.replace(hour=3, minute=15)

    # --- Pattern 4: Real Sybil — ONE nullifier shared across MANY wallets ---
    # This is the actual attack World ID's Sybil check exists to catch: a
    # single human hiding behind many wallets, all claiming under the same
    # human-proof. The previous version did the opposite (one wallet, many
    # nullifiers), which World would reject trivially and isn't the
    # interesting case.
    shared_sybil_nullifier = f"null_sybil_{secrets.token_hex(6)}"
    business_sybil = businesses.sample(1).iloc[0]
    time_base_sybil = datetime(2026, 9, 4, 12, 0, 0)

    for i in range(n_per_pattern):
        sybil_wallet = f"0x{secrets.token_hex(20)}"  # a fresh wallet per claim
        new_idx = len(df)
        df.loc[new_idx] = {
            'visit_id': f"v_fraud_p4_{i}",
            'wallet': sybil_wallet,
            'business_id': business_sybil['business_id'],
            'business_type': business_sybil['business_type'],
            'lat': business_sybil['lat'],
            'lon': business_sybil['lon'],
            'timestamp': time_base_sybil + timedelta(seconds=i * 3),
            'nullifier': shared_sybil_nullifier,  # SAME nullifier, many wallets
            'is_fraud': 1,
            'fraud_type': 'repeated_nullifier',
        }

    # Shuffle the resulting DataFrame
    df = df.sample(frac=1).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df_simulated = data_generate()
    print(f"Total records: {len(df_simulated)}")
    print(df_simulated['fraud_type'].value_counts(normalize=True))
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_simulated.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved to {OUTPUT_PATH}")
