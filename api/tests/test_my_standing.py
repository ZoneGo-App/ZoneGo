"""The personal view. A leaderboard nobody can find themselves on is a wall."""

from fastapi.testclient import TestClient

from api.main import app
from api.mock_data import MOCK_EXPLORERS

client = TestClient(app)

LEADER = MOCK_EXPLORERS[0].address
SECOND = MOCK_EXPLORERS[1].address


def me(address, **params):
    return client.get("/leaderboard/me", params={"address": address, **params})


def test_a_player_sees_their_own_points():
    body = me(LEADER).json()
    assert body["points"] == MOCK_EXPLORERS[0].points
    assert body["visits"] == MOCK_EXPLORERS[0].visits


def test_the_rank_comes_with_how_many_are_playing():
    """'12 of 47' means something. '12' on its own does not."""
    body = me(SECOND).json()
    assert body["rank"] == 2
    assert body["players"] == len(MOCK_EXPLORERS)


def test_it_says_how_far_the_next_place_is():
    body = me(SECOND).json()
    gap = MOCK_EXPLORERS[0].points - MOCK_EXPLORERS[1].points
    assert body["points_to_next"] == gap + 1


def test_whoever_is_first_has_nobody_to_chase():
    assert me(LEADER).json()["points_to_next"] is None


def test_a_zone_gives_a_smaller_pond():
    """The whole point of zones: first on your blocks is reachable."""
    everyone = me(SECOND).json()
    in_zone = me(SECOND, zone=MOCK_EXPLORERS[1].zone).json()
    assert in_zone["players"] < everyone["players"]
    assert in_zone["zone_name"] == "Lower East Side"


def test_a_wallet_with_no_visits_is_not_found():
    assert me("0x" + "f" * 40).status_code == 404


def test_a_malformed_address_is_refused():
    assert me("nope").status_code == 422
