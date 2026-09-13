import time

import pytest
from fastapi.testclient import TestClient

from api import chain, subgraph
from api.config import get_config
from api.main import app

client = TestClient(app)

VISITOR = "0x7A3c9E1b4D2f5A8c6B0e9F7d3C1a5B8e2D4f6A90"


def sign(campaign_id: int = 1, visitor: str = VISITOR):
    return client.post(
        "/qr/sign", json={"campaign_id": campaign_id, "visitor": visitor}
    )


def test_sign_returns_a_payload_for_a_real_campaign():
    r = sign()
    assert r.status_code == 200
    body = r.json()
    assert body["typed_data"]["primaryType"] == "VisitSig"
    assert body["typed_data"]["domain"]["chainId"] == 84532


def test_type_matches_the_contract_typehash():
    """Guards the one string that has to be identical in VisitRegistry.sol."""
    types = sign().json()["typed_data"]["types"]["VisitSig"]
    encoded = ",".join(f"{f['type']} {f['name']}" for f in types)
    assert encoded == (
        "uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash,address visitor"
    )


def test_payload_carries_the_campaign_geohash_as_bytes32():
    message = sign().json()["typed_data"]["message"]
    assert message["campaignId"] == 1
    # "dr5rsked" in ASCII, right-padded with zeros to 32 bytes.
    assert message["geohash"] == "0x" + b"dr5rsked".hex().ljust(64, "0")


def test_the_visitor_is_inside_the_signature():
    """The property this endpoint exists to guarantee.

    While `visitor` sat outside the signed struct, anyone holding the payload
    could call claim() with an address of their own and take the reward — and
    the payload is on a screen in a shop. Signing it binds the payment to one
    person, which is also why a merchant can no longer pre-sign one QR for the
    whole room.
    """
    message = sign().json()["typed_data"]["message"]
    assert message["visitor"] == VISITOR


def test_a_payload_is_good_for_one_visitor_only():
    a = sign(visitor=VISITOR).json()["typed_data"]["message"]["visitor"]
    b = sign(visitor="0x" + "1" * 40).json()["typed_data"]["message"]["visitor"]
    assert a != b


def test_a_malformed_visitor_is_rejected():
    assert sign(visitor="0x1").status_code == 422


def test_the_visitor_is_required():
    assert client.post("/qr/sign", json={"campaign_id": 1}).status_code == 422


def test_every_call_gets_a_fresh_nonce():
    assert sign().json()["nonce"] != sign().json()["nonce"]


JS_MAX_SAFE_INTEGER = 2**53 - 1


def test_the_nonce_travels_as_a_string():
    """Past 2**53 a JavaScript number stops being exact, and `JSON.parse`
    rounds without saying so. The wallet would sign a nonce that was never
    issued, every claim would revert, and nothing would name the cause."""
    body = sign().json()
    assert isinstance(body["nonce"], str)
    assert isinstance(body["typed_data"]["message"]["nonce"], str)
    assert body["nonce"] == body["typed_data"]["message"]["nonce"]


def test_the_nonce_is_usually_too_big_for_a_javascript_number():
    """Not an edge case worth guarding — it is the normal case.

    A 64-bit random clears the safe range about 2047 times out of 2048, so
    twenty draws landing inside it would mean the nonce shrank, not that the
    test got lucky.
    """
    drawn = [int(sign().json()["nonce"]) for _ in range(20)]
    assert any(n > JS_MAX_SAFE_INTEGER for n in drawn)


def test_signature_outlives_the_qr_on_screen():
    r = sign().json()
    assert r["expiry"] > time.time() + 60
    assert r["rotate_after_seconds"] < r["expiry"] - time.time()


def test_unknown_campaign_returns_404():
    assert sign(campaign_id=999).status_code == 404


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
    assert sign().status_code == 200


def test_the_signed_geohash_is_the_one_the_contract_holds(live):
    """A payload built from a stale geohash is a signature that fails on chain."""
    message = sign().json()["typed_data"]["message"]
    assert message["geohash"] == "0x" + b"dr5rsm47".hex().ljust(64, "0")


def test_a_campaign_that_is_not_on_chain_is_404_when_live(live):
    assert sign(campaign_id=999).status_code == 404
