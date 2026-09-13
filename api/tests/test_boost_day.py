"""The one lever a merchant has: one day a week, twice the reward.

Every store pays the same base, so a big chain cannot outbid the bodega next
door for a visitor's attention. What varies is a single day each week that any
store can pick, and the arithmetic that turns it into what a visit is worth
right now.
"""

from fastapi.testclient import TestClient

from api.main import app
from api.mock_data import DAILY_CAP, REWARD_PER_VISIT
from api.points import unix_day
from api.schemas import Campaign

client = TestClient(app)


def campaign(**overrides) -> Campaign:
    fields = dict(
        campaign_id=1,
        merchant="0x" + "1" * 40,
        merchant_name="A Store",
        category="corner_store",
        sells="coffee",
        reward_per_visit=REWARD_PER_VISIT,
        daily_cap=DAILY_CAP,
        lat=40.7185,
        lon=-73.9880,
        geohash="dr5rsked",
        radius_meters=120,
        balance=1_000_000,
    )
    return Campaign(**{**fields, **overrides})


# --- the arithmetic ---------------------------------------------------------


def test_a_store_boosting_today_pays_double():
    c = campaign(boost_day=unix_day())
    assert c.pays_double_today
    assert c.reward_today == REWARD_PER_VISIT * 2


def test_a_store_with_no_boost_day_pays_the_base():
    c = campaign()
    assert not c.pays_double_today
    assert c.reward_today == REWARD_PER_VISIT


def test_a_boost_day_still_to_come_does_not_pay_double_yet():
    """The point of announcing it early is that people plan the walk."""
    c = campaign(boost_day=unix_day() + 3)
    assert not c.pays_double_today
    assert c.reward_today == REWARD_PER_VISIT


def test_a_boost_day_that_already_passed_pays_the_base_again():
    c = campaign(boost_day=unix_day() - 1)
    assert not c.pays_double_today


def test_the_base_reward_is_never_overwritten():
    """`reward_per_visit` is what the chain holds; the doubling is derived.

    A merchant panel has to show both, and a claim is validated against the
    stored value, so overwriting it with today's number would make the two
    disagree on the one day it matters.
    """
    c = campaign(boost_day=unix_day())
    assert c.reward_per_visit == REWARD_PER_VISIT
    assert c.reward_today == REWARD_PER_VISIT * 2


# --- what the API hands the frontend ---------------------------------------


def test_the_campaign_route_exposes_what_a_visit_is_worth_now():
    body = client.get("/campaigns/1").json()
    assert body["reward_today"] == body["reward_per_visit"] * 2
    assert body["pays_double_today"] is True


def test_search_carries_the_boost_through():
    """The search screen is where a visitor decides the route, so it needs the
    number that decides it."""
    hits = client.get(
        "/search", params={"lat": 40.7190, "lon": -73.9882, "radius_km": 1}
    ).json()
    boosting = [h["campaign"] for h in hits if h["campaign"]["pays_double_today"]]
    assert boosting, "the samples should always have one store doubling today"
    assert boosting[0]["reward_today"] == boosting[0]["reward_per_visit"] * 2


# --- the pricing decision itself -------------------------------------------


def test_every_sample_store_pays_the_same_base():
    """Pricing by store size was dropped: it made the big store always worth
    more than the bodega, which is the opposite of what this is for."""
    campaigns = client.get("/campaigns").json()
    assert len({c["reward_per_visit"] for c in campaigns}) == 1


def test_every_sample_store_carries_the_same_daily_cap():
    campaigns = client.get("/campaigns").json()
    assert {c["daily_cap"] for c in campaigns} == {DAILY_CAP}
