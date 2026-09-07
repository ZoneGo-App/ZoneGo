import time

import pytest
from fastapi.testclient import TestClient

from api import chain, subgraph
from api.config import get_config
from api.main import app

client = TestClient(app)

VISITOR = "0x" + "a1" * 20
SIGNATURE = "0x" + "b2" * 65
GEOHASH = "0x" + b"dr5rsked".hex().ljust(64, "0")


def a_claim(**overrides):
    body = {
        "campaign_id": 1,
        "nonce": 12345,
        "expiry": int(time.time()) + 90,
        "geohash": GEOHASH,
        "signature": SIGNATURE,
        "visitor": VISITOR,
        "world_proof": "",
    }
    body.update(overrides)
    return body


def test_a_valid_claim_comes_back_with_a_hash():
    r = client.post("/visits/claim", json=a_claim())
    assert r.status_code == 200
    assert r.json()["tx_hash"].startswith("0x")
    assert r.json()["relayed"] is True


def test_an_expired_signature_is_refused():
    """A photographed QR used two minutes later must not reach the chain."""
    r = client.post("/visits/claim", json=a_claim(expiry=int(time.time()) - 1))
    assert r.status_code == 410


def test_a_malformed_signature_never_costs_gas():
    r = client.post("/visits/claim", json=a_claim(signature="0xdeadbeef"))
    assert r.status_code == 422


def test_a_malformed_address_is_refused():
    r = client.post("/visits/claim", json=a_claim(visitor="not-an-address"))
    assert r.status_code == 422


def test_unknown_campaign_returns_404():
    r = client.post("/visits/claim", json=a_claim(campaign_id=999))
    assert r.status_code == 404


def test_a_geohash_from_another_store_is_refused():
    elsewhere = "0x" + b"dr5rsm47".hex().ljust(64, "0")
    r = client.post("/visits/claim", json=a_claim(geohash=elsewhere))
    assert r.status_code == 409


def test_the_same_claim_is_idempotent_in_mock_mode():
    a = client.post("/visits/claim", json=a_claim()).json()["tx_hash"]
    b = client.post("/visits/claim", json=a_claim()).json()["tx_hash"]
    assert a == b


ON_CHAIN = chain.OnChainCampaign(
    campaign_id=1,
    merchant="0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03",
    reward_per_visit=50_000,
    daily_cap=60,
    geohash="dr5rsked",
    lat=40.7185,
    lon=-73.9880,
    radius_meters=120,
    balance=48_500_000,
)


@pytest.fixture
def live(monkeypatch):
    """Live mode with the chain as the only source, the way it starts out."""
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(subgraph, "get_campaign", lambda campaign_id: None)
    monkeypatch.setattr(
        chain, "get_campaign", lambda campaign_id: ON_CHAIN if campaign_id == 1 else None
    )


def test_a_real_campaign_gets_past_validation(live):
    """501 and not 404: it reached the part that is genuinely missing.

    The sample campaigns are not a source once the contracts are live, and
    validating against them refused every real claim before it got here.
    """
    r = client.post("/visits/claim", json=a_claim())
    assert r.status_code == 501


def test_an_unknown_campaign_is_still_404_when_live(live):
    r = client.post("/visits/claim", json=a_claim(campaign_id=999))
    assert r.status_code == 404


def test_the_geohash_is_checked_against_the_chain_not_the_samples(live):
    elsewhere = "0x" + b"dr5rsm47".hex().ljust(64, "0")
    r = client.post("/visits/claim", json=a_claim(geohash=elsewhere))
    assert r.status_code == 409


def test_a_campaign_out_of_funds_never_reaches_the_chain(live, monkeypatch):
    broke = chain.OnChainCampaign(**{**ON_CHAIN.__dict__, "balance": 0})
    monkeypatch.setattr(chain, "get_campaign", lambda campaign_id: broke)
    r = client.post("/visits/claim", json=a_claim())
    assert r.status_code == 409
