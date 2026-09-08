"""Geographic helpers: distance and geohash, with no external dependency.

Geohash is what the contract stores for a campaign, so the encoder here has to
match whatever the contract ends up doing. Precision 8 gives a cell of roughly
38 x 19 metres, which is finer than the smallest radius we accept.
"""

from math import asin, cos, radians, sin, sqrt

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
EARTH_RADIUS_M = 6_371_000

# A zone is just a shorter geohash. Six characters is a cell of roughly
# 1200 x 600 metres — about the size of a neighbourhood, and small enough that
# being first in it is something a person can actually do.
#
# Deriving zones this way means we need no map data, no city dataset and no
# API: the zone is already on chain inside the campaign's geohash, so anyone
# can verify which zone a store belongs to. It also works unchanged in any
# city in the world.
ZONE_PRECISION = 6


def zone_of(geohash: str) -> str:
    if len(geohash) < ZONE_PRECISION:
        raise ValueError(f"geohash too short to hold a zone: {geohash!r}")
    return geohash[:ZONE_PRECISION]


def encode_geohash(lat: float, lon: float, precision: int = 8) -> str:
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    out: list[str] = []
    bits = 0
    bit_count = 0
    even = True

    while len(out) < precision:
        if even:
            mid = sum(lon_range) / 2
            if lon > mid:
                bits = (bits << 1) | 1
                lon_range[0] = mid
            else:
                bits <<= 1
                lon_range[1] = mid
        else:
            mid = sum(lat_range) / 2
            if lat > mid:
                bits = (bits << 1) | 1
                lat_range[0] = mid
            else:
                bits <<= 1
                lat_range[1] = mid

        even = not even
        bit_count += 1
        if bit_count == 5:
            out.append(BASE32[bits])
            bits = 0
            bit_count = 0

    return "".join(out)


def decode_geohash(geohash: str) -> tuple[float, float]:
    """Centre of the cell, as (lat, lon).

    The chain stores a geohash, not coordinates, so this is how a campaign read
    back from the subgraph gets a point to measure distance from. Precision 8
    puts that centre within about twenty metres of the real door, which is well
    inside the smallest radius anyone can pick.
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    even = True

    for char in geohash:
        index = BASE32.find(char)
        if index < 0:
            raise ValueError(f"not a geohash character: {char!r}")
        for shift in (4, 3, 2, 1, 0):
            bit = (index >> shift) & 1
            target = lon_range if even else lat_range
            mid = sum(target) / 2
            if bit:
                target[0] = mid
            else:
                target[1] = mid
            even = not even

    return sum(lat_range) / 2, sum(lon_range) / 2


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance. Good enough at city scale, and cheap."""
    p1, p2 = radians(lat1), radians(lat2)
    d_lat = p2 - p1
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(p1) * cos(p2) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))
