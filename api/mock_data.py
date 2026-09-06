from datetime import datetime, timedelta, timezone

from api.schemas import Campaign

NOW = datetime.now(timezone.utc)

CAMPAIGNS = [
    Campaign(
        campaign_id=1,
        merchant="0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03",
        merchant_name="Panaderia San Jose",
        category="bakery",
        reward_per_visit=250000,
        daily_cap=40,
        geohash="6mc5rvw2",
        radius_meters=120,
        balance=48500000,
        created_at=NOW - timedelta(days=2),
    ),
    Campaign(
        campaign_id=2,
        merchant="0x9aB4c3D2e1F0a9B8c7D6e5F4a3B2c1D0e9F8a7B6",
        merchant_name="Bodega Dona Rosa",
        category="corner_store",
        reward_per_visit=150000,
        daily_cap=60,
        geohash="6mc5rvx7",
        radius_meters=80,
        balance=22000000,
        created_at=NOW - timedelta(days=1),
    ),
    Campaign(
        campaign_id=3,
        merchant="0x3C2b1A0f9E8d7C6b5A4f3E2d1C0b9A8f7E6d5C4b",
        merchant_name="Menu Criollo El Rincon",
        category="restaurant",
        reward_per_visit=400000,
        daily_cap=25,
        geohash="6mc5rvz1",
        radius_meters=150,
        balance=9800000,
        created_at=NOW - timedelta(hours=20),
    ),
]
