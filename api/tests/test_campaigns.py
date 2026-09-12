"""The campaign routes, where the index and the vault meet.

The interesting cases are all in live mode: which of the two sources answered,
what happens when one of them is down, and — the one that matters today — that
a position read off the chain wins over the one the index has, because
`CampaignCreated` does not carry a geohash yet.
"""

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api import chain, subgraph
from api.config import get_config
from api.main import app
from api.schemas import Campaign

client = TestClient(app)

MERCHANT = "0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03"

# What the index gives back today: everything except a place to stand. An empty
# geohash decodes to (0, 0), so this is the shape of the bug, not an invention.
INDEXED = Campaign(
    campaign_id=1,
    merchant=MERCHANT,
    merchant_name="Merchant 0x1F6B…9e03",
    category="",
    sells="",
    reward_per_visit=50_000,
    daily_cap=60,
    lat=0.0,
    lon=0.0,
    geohash="",
    radius_meters=1,
    balance=48_500_000,
    created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
)

ON_CHAIN = chain.OnChainCampaign(
    campaign_id=1,
    merchant=MERCHANT,
    reward_per_visit=50_000,
    daily_cap=60,
    geohash="dr5rsked",
    lat=40.7185,
    lon=-73.9880,
    radius_meters=120,
    balance=47_000_000,
)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)


def sources(monkeypatch, *, indexed, onchain):
    """Stand in for both sources. Raise an exception to make one fail."""

    def from_index(campaign_id):
        if isinstance(indexed, Exception):
            raise indexed
        return indexed

    def from_chain(campaign_id):
        if isinstance(onchain, Exception):
            raise onchain
        return onchain

    monkeypatch.setattr(subgraph, "get_campaign", from_index)
    monkeypatch.setattr(chain, "get_campaign", from_chain)


def test_mock_mode_still_answers_without_either_source():
    assert len(client.get("/campaigns").json()) == 3
    assert client.get("/campaigns/1").json()["merchant_name"] == "Delancey Bodega"


def test_an_unknown_campaign_is_404_in_mock_mode():
    assert client.get("/campaigns/999").status_code == 404


def test_the_chain_position_wins_over_the_index(live, monkeypatch):
    """The point of the overlay: the index cannot place a campaign yet."""
    sources(monkeypatch, indexed=INDEXED, onchain=ON_CHAIN)
    body = client.get("/campaigns/1").json()
    assert body["geohash"] == "dr5rsked"
    assert body["radius_meters"] == 120
    assert 40.71 < body["lat"] < 40.73


def test_the_balance_comes_from_the_chain_not_the_index(live, monkeypatch):
    sources(monkeypatch, indexed=INDEXED, onchain=ON_CHAIN)
    assert client.get("/campaigns/1").json()["balance"] == 47_000_000


def test_a_campaign_drained_since_the_last_block_stops_being_active(live, monkeypatch):
    """Overlaying the balance without the flag that depends on it was the bug.

    The index is a block behind and still shows money; the vault says it is
    spent. Whoever walks there cannot be paid, so search has to stop offering
    it the moment the chain says so.
    """
    sources(monkeypatch, indexed=INDEXED, onchain=replace(ON_CHAIN, balance=0))
    body = client.get("/campaigns/1").json()
    assert body["balance"] == 0
    assert body["active"] is False


def test_a_campaign_the_index_switched_off_is_not_revived_by_a_balance(live, monkeypatch):
    """The overlay only ever narrows: the vault cannot see the off switch."""
    sources(monkeypatch, indexed=INDEXED.model_copy(update={"active": False}), onchain=ON_CHAIN)
    assert client.get("/campaigns/1").json()["active"] is False


def test_the_index_still_supplies_what_the_chain_has_no_room_for(live, monkeypatch):
    sources(monkeypatch, indexed=INDEXED, onchain=ON_CHAIN)
    assert client.get("/campaigns/1").json()["created_at"] is not None


def test_a_node_we_cannot_reach_does_not_fail_the_request(live, monkeypatch):
    """A stale answer beats no answer when the index already replied."""
    sources(monkeypatch, indexed=INDEXED, onchain=chain.ChainError("no rpc"))
    r = client.get("/campaigns/1")
    assert r.status_code == 200
    assert r.json()["balance"] == 48_500_000


def test_a_campaign_the_index_has_not_seen_comes_from_the_chain(live, monkeypatch):
    """Created seconds ago: on chain a block before it is anywhere else."""
    sources(monkeypatch, indexed=None, onchain=ON_CHAIN)
    body = client.get("/campaigns/1").json()
    assert body["geohash"] == "dr5rsked"
    # Only an index knows when something happened, so this stays empty rather
    # than being filled with the moment we happened to ask.
    assert body["created_at"] is None


def test_a_campaign_in_neither_source_is_404(live, monkeypatch):
    sources(monkeypatch, indexed=None, onchain=None)
    assert client.get("/campaigns/1").status_code == 404


def test_the_chain_answers_when_the_index_is_down(live, monkeypatch):
    sources(monkeypatch, indexed=subgraph.SubgraphError("down"), onchain=ON_CHAIN)
    assert client.get("/campaigns/1").status_code == 200


def test_both_sources_down_is_502(live, monkeypatch):
    sources(
        monkeypatch,
        indexed=subgraph.SubgraphError("down"),
        onchain=chain.ChainError("no rpc"),
    )
    assert client.get("/campaigns/1").status_code == 502
