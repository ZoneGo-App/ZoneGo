from api.geo import decode_geohash, distance_meters, encode_geohash

DELANCEY = (40.7185, -73.9880)


def test_lower_east_side_encodes_into_the_nyc_cell():
    assert encode_geohash(*DELANCEY).startswith("dr5r")


def test_decoding_lands_back_within_twenty_metres():
    lat, lon = decode_geohash(encode_geohash(*DELANCEY))
    assert distance_meters(*DELANCEY, lat, lon) < 20


def test_distance_between_two_lower_east_side_corners():
    metres = distance_meters(40.7185, -73.9880, 40.7215, -73.9895)
    assert 300 < metres < 400


def test_same_point_is_zero_metres_apart():
    assert distance_meters(*DELANCEY, *DELANCEY) == 0


def test_a_bad_character_is_rejected():
    try:
        decode_geohash("dr5rsk?d")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
