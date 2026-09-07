"""Sample campaigns so the frontend can build before the contracts are live.

Real stores around Delancey and Orchard, Lower East Side. Coordinates are the
ones the synthetic generator uses too, so the mock API and Edmer's dataset
describe the same neighbourhood.

Amounts are USDC minor units — 6 decimals, so 50_000 is five cents.
"""

from datetime import datetime, timedelta, timezone

from api.geo import encode_geohash
from api.schemas import Campaign

NOW = datetime.now(timezone.utc)


def _campaign(**kwargs) -> Campaign:
    """Fills in the geohash so the two can never drift apart."""
    kwargs["geohash"] = encode_geohash(kwargs["lat"], kwargs["lon"])
    return Campaign(**kwargs)


CAMPAIGNS = [
    _campaign(
        campaign_id=1,
        merchant="0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03",
        merchant_name="Delancey Bodega",
        category="corner_store",
        # The demo case: Google files this as a convenience store and would
        # never surface it for "sneakers". The owner knows better.
        sells="coffee, sandwiches, phone chargers, running sneakers, socks",
        reward_per_visit=50_000,
        daily_cap=60,
        lat=40.7185,
        lon=-73.9880,
        radius_meters=120,
        balance=48_500_000,
        created_at=NOW - timedelta(days=2),
    ),
    _campaign(
        campaign_id=2,
        merchant="0x9aB4c3D2e1F0a9B8c7D6e5F4a3B2c1D0e9F8a7B6",
        merchant_name="Kim's Sneakers",
        category="footwear",
        sells="sneakers, running shoes, basketball shoes, laces",
        reward_per_visit=150_000,
        daily_cap=40,
        lat=40.7205,
        lon=-73.9885,
        radius_meters=80,
        balance=22_000_000,
        created_at=NOW - timedelta(days=1),
    ),
    _campaign(
        campaign_id=3,
        merchant="0x3C2b1A0f9E8d7C6b5A4f3E2d1C0b9A8f7E6d5C4b",
        merchant_name="Orchard Street Kicks",
        category="footwear",
        sells="vintage sneakers, streetwear, caps",
        reward_per_visit=120_000,
        daily_cap=25,
        lat=40.7215,
        lon=-73.9895,
        radius_meters=150,
        balance=9_800_000,
        created_at=NOW - timedelta(hours=20),
    ),
]
