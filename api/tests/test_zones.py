import pytest

from api.geo import ZONE_PRECISION, decode_geohash, distance_meters, encode_geohash, zone_of
from api.mock_data import CAMPAIGNS
from api.zones import name_for_geohash, zone_name

DELANCEY = (40.7185, -73.9880)


def test_a_zone_is_the_geohash_prefix():
    assert zone_of("dr5rsked") == "dr5rsk"
    assert len(zone_of(encode_geohash(*DELANCEY))) == ZONE_PRECISION


def test_two_stores_on_the_same_blocks_share_a_zone():
    kims, orchard = CAMPAIGNS[1], CAMPAIGNS[2]
    assert zone_of(CAMPAIGNS[0].geohash) == zone_of(kims.geohash)
    # Orchard Street Kicks sits north of the other two, in its own cell.
    assert zone_of(orchard.geohash) != zone_of(kims.geohash)


def test_a_zone_is_neighbourhood_sized():
    """Around a kilometre across — winnable, not a whole borough."""
    lat, lon = decode_geohash(zone_of(encode_geohash(*DELANCEY)))
    assert distance_meters(*DELANCEY, lat, lon) < 900


def test_known_zones_get_a_readable_name():
    assert name_for_geohash(CAMPAIGNS[0].geohash) == "Lower East Side"


def test_an_unnamed_zone_falls_back_to_the_prefix():
    """A block nobody named still ranks and still pays."""
    assert zone_name("zzzzzz") == "zzzzzz"


def test_a_short_geohash_is_refused():
    with pytest.raises(ValueError):
        zone_of("dr5")
