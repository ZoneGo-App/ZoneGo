"""The subgraph client, exercised against canned answers.

No network here: what matters is that a GraphQL node turns into a Campaign the
rest of the API can use, and that failures surface as failures instead of as
empty results.
"""

import httpx
import pytest

from api import subgraph
from api.config import get_config
from api.eip712 import geohash_to_bytes32

NODE = {
    "id": "0x01",
    "campaignId": "1",
    "merchant": {"id": "0x1f6bfd8f9242ac5eef6b21082a9c460907e39e03"},
    "rewardPerVisit": "50000",
    "dailyCap": "60",
    "geohash": geohash_to_bytes32("dr5rsked"),
    "radiusMeters": "120",
    "balance": "48500000",
    "active": True,
    "createdAt": "1788700000",
    "visitCount": 7,
    "totalPaid": "350000",
}


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    monkeypatch.setattr(get_config(), "subgraph_url", "https://example.test/gql")
    subgraph.clear_cache()
    yield
    subgraph.clear_cache()


def answer(monkeypatch, payload):
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def test_a_node_becomes_a_campaign(monkeypatch):
    answer(monkeypatch, {"data": {"campaigns": [NODE]}})
    campaign = subgraph.list_campaigns()[0]
    assert campaign.campaign_id == 1
    assert campaign.reward_per_visit == 50_000
    assert campaign.balance == 48_500_000


def test_the_geohash_comes_back_as_coordinates(monkeypatch):
    answer(monkeypatch, {"data": {"campaigns": [NODE]}})
    campaign = subgraph.list_campaigns()[0]
    assert campaign.geohash == "dr5rsked"
    assert 40.71 < campaign.lat < 40.73
    assert -73.99 < campaign.lon < -73.98


def test_a_graphql_error_is_not_an_empty_result(monkeypatch):
    """GraphQL answers 200 with an errors array — the trap this guards."""
    answer(monkeypatch, {"errors": [{"message": "store not indexed"}]})
    with pytest.raises(subgraph.SubgraphError):
        subgraph.list_campaigns()


def test_a_missing_url_fails_loudly(monkeypatch):
    monkeypatch.setattr(get_config(), "subgraph_url", "")
    with pytest.raises(subgraph.SubgraphError):
        subgraph.list_campaigns()


def test_repeated_queries_hit_the_cache(monkeypatch):
    calls = answer(monkeypatch, {"data": {"campaigns": [NODE]}})
    subgraph.list_campaigns()
    subgraph.list_campaigns()
    assert calls["n"] == 1


def test_an_unknown_campaign_is_none(monkeypatch):
    answer(monkeypatch, {"data": {"campaign": None}})
    assert subgraph.get_campaign(999) is None
