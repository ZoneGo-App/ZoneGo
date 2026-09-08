import time

import pytest
from fastapi.testclient import TestClient

from api import chain, subgraph
from api.config import get_config
from api.main import app

client = TestClient(app)


def test_sign_returns_a_payload_for_a_real_campaign():
    r = client.post("/qr/sign", json={"campaign_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["typed_data"]["primaryType"] == "VisitSig"
    assert body["typed_data"]["domain"]["chainId"] == 84532


def test_type_matches_the_contract_typehash():
    """Guards the one string that has to be identical in VisitRegistry.sol."""
    fields = client.post("/qr/sign", json={"campaign_id": 1}).json()
    types = fields["typed_data"]["types"]["VisitSig"]
    encoded = ",".join(f"{f['type']} {f['name']}" for f in types)
    assert encoded == "uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash"


def test_payload_carries_the_campaign_geohash_as_bytes32():
    r = client.post("/qr/sign", json={"campaign_id": 1})
    message = r.json()["typed_data"]["message"]
    assert message["campaignId"] == 1
    # "dr5rsked" in ASCII, right-padded with zeros to 32 bytes.
    assert message["geohash"] == "0x" + b"dr5rsked".hex().ljust(64, "0")


def test_the_visitor_is_not_in_the_signature():
    """The merchant signs one QR for everyone, so it cannot name a visitor."""
    r = client.post("/qr/sign", json={"campaign_id": 1})
    assert "visitor" not in r.json()["typed_data"]["message"]


def test_every_call_gets_a_fresh_nonce():
    a = client.post("/qr/sign", json={"campaign_id": 1}).json()["nonce"]
    b = client.post("/qr/sign", json={"campaign_id": 1}).json()["nonce"]
    assert a != b


def test_signature_outlives_the_qr_on_screen():
    r = client.post("/qr/sign", json={"campaign_id": 1}).json()
    assert r["expiry"] > time.time() + 60
    assert r["rotate_after_seconds"] < r["expiry"] - time.time()


def test_unknown_campaign_returns_404():
    assert client.post("/qr/sign", json={"campaign_id": 999}).status_code == 404


ON_CHAIN = chain.OnChainCampaign(
    campaign_id=1,
    merchant="0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03",
    reward_per_visit=50_000,
    daily_cap=60,
    geohash="dr5rsm47",
    lat=40.7205,
    lon=-73.9855,
    radius_meters=120,
    balance=48_500_000,
)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(subgraph, "get_campaign", lambda campaign_id: None)
    monkeypatch.setattr(
        chain, "get_campaign", lambda campaign_id: ON_CHAIN if campaign_id == 1 else None
    )


def test_a_merchant_can_sign_against_a_real_campaign(live):
    """Used to be a 501: the payload was only buildable from the samples."""
    assert client.post("/qr/sign", json={"campaign_id": 1}).status_code == 200


def test_the_signed_geohash_is_the_one_the_contract_holds(live):
    """A payload built from a stale geohash is a signature that fails on chain."""
    message = client.post("/qr/sign", json={"campaign_id": 1}).json()["typed_data"]["message"]
    assert message["geohash"] == "0x" + b"dr5rsm47".hex().ljust(64, "0")


def test_a_campaign_that_is_not_on_chain_is_404_when_live(live):
    assert client.post("/qr/sign", json={"campaign_id": 999}).status_code == 404
