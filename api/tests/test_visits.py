import time

import pytest
from fastapi.testclient import TestClient

from api import chain, relay, subgraph
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


def test_a_nonce_sent_as_a_string_is_accepted():
    """/qr/sign hands it over as a string, so a claim can send it back as one.

    A frontend should never have to convert a value we gave it — and if it
    tried, converting it through a JavaScript number is exactly the rounding
    the string was there to avoid.
    """
    big = "12637475492468184470"
    r = client.post("/visits/claim", json=a_claim(nonce=big))
    assert r.status_code == 200


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


NULLIFIER = "0x" + "c3" * 32
SUBMITTED = "0x" + "ab" * 32
ATTESTER_SIGNATURE = "0x" + "d4" * 65


def an_attestation(**overrides):
    """What POST /world/verify hands back, as the claim body carries it."""
    body = {
        "visitor": VISITOR,
        "nullifier_hash": NULLIFIER,
        "expiry": int(time.time()) + 120,
        "signature": ATTESTER_SIGNATURE,
        "typed_data": {},
    }
    body.update(overrides)
    return body


@pytest.fixture
def live(monkeypatch):
    """Live mode with the chain as the only source, the way it starts out."""
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(subgraph, "get_campaign", lambda campaign_id: None)
    monkeypatch.setattr(
        chain, "get_campaign", lambda campaign_id: ON_CHAIN if campaign_id == 1 else None
    )
    monkeypatch.setattr(relay, "send_claim", lambda claim: SUBMITTED)


def test_a_real_campaign_is_submitted_to_the_chain(live):
    """Validated against the contract, then relayed — not the sample data."""
    r = client.post("/visits/claim", json=a_claim(attestation=an_attestation()))
    assert r.status_code == 200
    assert r.json()["tx_hash"] == SUBMITTED
    assert r.json()["status"] == "submitted"


def test_the_signed_fields_are_passed_through_untouched(live, monkeypatch):
    seen = {}
    monkeypatch.setattr(relay, "send_claim", lambda claim: seen.setdefault("c", claim) and SUBMITTED)
    client.post("/visits/claim", json=a_claim(attestation=an_attestation()))
    assert seen["c"].signature == SIGNATURE
    assert seen["c"].visitor == VISITOR
    # Read off the attestation, which is where the contract reads it from too.
    assert seen["c"].nullifier_hash == NULLIFIER
    assert seen["c"].attestation_signature == ATTESTER_SIGNATURE


def test_a_claim_without_an_attestation_is_refused(live):
    """No attestation means no nullifier, and a zero would misprice rewards.

    Every visitor would land in one weekly bucket, so the second person to
    claim anywhere would be paid 50% of what was their first visit.
    """
    assert client.post("/visits/claim", json=a_claim()).status_code == 400


def test_an_expired_attestation_is_refused_before_it_costs_gas(live):
    """Its own clock: the QR may be fresh and the World session long over."""
    stale = an_attestation(expiry=int(time.time()) - 1)
    r = client.post("/visits/claim", json=a_claim(attestation=stale))
    assert r.status_code == 410


def test_an_attestation_for_somebody_else_is_refused(live):
    """The contract reverts on this. Finding out here is free."""
    someone_else = an_attestation(visitor="0x" + "e5" * 20)
    r = client.post("/visits/claim", json=a_claim(attestation=someone_else))
    assert r.status_code == 400


def test_a_loose_nullifier_contradicting_the_attestation_is_refused(live):
    """Two answers to one question, so refuse rather than pick one quietly."""
    r = client.post(
        "/visits/claim",
        json=a_claim(attestation=an_attestation(), nullifier_hash="0x" + "f6" * 32),
    )
    assert r.status_code == 400


def test_a_loose_nullifier_that_agrees_is_accepted(live):
    """Redundant is not wrong: a caller sending both is only repeating itself."""
    r = client.post(
        "/visits/claim",
        json=a_claim(attestation=an_attestation(), nullifier_hash=NULLIFIER),
    )
    assert r.status_code == 200


def test_a_relay_failure_is_502_not_500(live, monkeypatch):
    def boom(claim):
        raise relay.RelayError("node unreachable")

    monkeypatch.setattr(relay, "send_claim", boom)
    r = client.post("/visits/claim", json=a_claim(attestation=an_attestation()))
    assert r.status_code == 502


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
