"""Sample campaigns so the frontend can build before the contracts are live.

Real stores around Delancey and Orchard, Lower East Side. Coordinates are the
ones the synthetic generator uses too, so the mock API and Edmer's dataset
describe the same neighbourhood.

Amounts are USDC minor units — 6 decimals, so 50_000 is five cents.
"""

from datetime import datetime, timedelta, timezone

from api.geo import encode_geohash, zone_of
from api.schemas import Campaign, LeaderboardEntry
from api.zones import zone_name

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


def _entry(rank, address, visits, distinct=None, zone=None) -> LeaderboardEntry:
    return LeaderboardEntry(
        rank=rank,
        address=address,
        label=f"{address[:6]}…{address[-4:]}",
        visits=visits,
        distinct_merchants=distinct,
        zone=zone,
        zone_name=zone_name(zone) if zone else None,
    )


# Seeded so David has a table to build against and the demo has something to
# show. Explorers are ordered by visits, but the interesting column is how
# many different stores each one found.
LES = zone_of(CAMPAIGNS[0].geohash)
NORTH = zone_of(CAMPAIGNS[2].geohash)

MOCK_EXPLORERS = [
    _entry(1, "0x7A3c9E1b4D2f5A8c6B0e9F7d3C1a5B8e2D4f6A90", 142, 9, LES),
    _entry(2, "0x4E8b2C7a1F9d6B3e5A0c8D2f7B4a1E6c9D3f5B70", 97, 5, LES),
    _entry(3, "0xB1d5F8a3C6e9D2b7A4f0E8c1D5b9F3a6C2e7D480", 88, 11, NORTH),
    _entry(4, "0x2F7a9D4c1B8e6A3f5C0d7E2b9A4f1C6d3B8e5A20", 61, 4, LES),
    _entry(5, "0xC9e4B7a2D5f8C1b6E3a0F9d4B7c2A5e8D1f6C390", 45, 7, NORTH),
]

MOCK_MERCHANTS = [
    _entry(1, CAMPAIGNS[0].merchant, 412, zone=LES),
    _entry(2, CAMPAIGNS[1].merchant, 287, zone=zone_of(CAMPAIGNS[1].geohash)),
    _entry(3, CAMPAIGNS[2].merchant, 203, zone=NORTH),
]
