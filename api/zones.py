"""Human names for the zones the chain knows only as geohash prefixes.

The zone itself is derived from the chain and needs nothing from us. This file
only decides what to call it on screen, because "dr5rsk" means nothing to
somebody standing on Delancey Street.

Anything not listed falls back to the prefix. A zone with no name still ranks,
still pays and still works — it just shows up unlabelled, which is the right
failure: the leaderboard should never hide a store because we did not get
around to naming its block.
"""

from api.geo import zone_of

# Lower East Side and the blocks just north of Houston. Enough for the seeded
# demo campaigns; the full map of New York is not something this needs.
ZONE_NAMES = {
    "dr5rsk": "Lower East Side",
    "dr5rsm": "East Village",
    "dr5rsj": "Two Bridges",
    "dr5rsu": "Nolita",
}


def zone_name(zone: str) -> str:
    return ZONE_NAMES.get(zone, zone)


def name_for_geohash(geohash: str) -> str:
    return zone_name(zone_of(geohash))
