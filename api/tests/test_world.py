"""The World bridge, and the trust it introduces.

Selfie Check cannot be verified on chain, so the contract has to believe a
signature of ours. These tests are about the fence around that: the signature
names one wallet, dies in two minutes, and a human cannot collect one for a
second address.
"""

import time

import httpx
import pytest
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient
from web3 import Web3

from api import world
from api.config import get_config
from api.main import app

client = TestClient(app)

# A key that exists only here. Anything real lives in .env and never in a test.
ATTESTER_KEY = "0x" + "11" * 32
ATTESTER = Account.from_key(ATTESTER_KEY).address

VISITOR = "0x7A3c9E1b4D2f5A8c6B0e9F7d3C1a5B8e2D4f6A90"
OTHER = "0x4E8b2C7a1F9d6B3e5A0c8D2f7B4a1E6c9D3f5B70"
NULLIFIER = "0x" + "ab" * 32
REGISTRY = "0xed168b6B9c96f59Be1AD3866F24e8851D3Afca4e"

A_PROOF = {"protocol_version": "4.0", "action": "verify-visitor", "responses": []}


@pytest.fixture
def live(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "mock_mode", False)
    monkeypatch.setattr(config, "attester_private_key", ATTESTER_KEY)
    monkeypatch.setattr(config, "world_rp_id", "rp_test")
    monkeypatch.setattr(config, "visit_registry_address", REGISTRY)


def world_says(monkeypatch, payload, status=200):
    def fake_post(url, **kwargs):
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)


def verified(nullifier=NULLIFIER):
    return {"success": True, "nullifier": nullifier, "action": "verify-visitor"}


# --- talking to World -------------------------------------------------------


def test_a_proof_for_another_action_is_refused_before_asking_world(live, monkeypatch):
    """Nullifiers differ per action, so any action would mean a wallet per action."""
    asked = []
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: asked.append(args))
    r = client.post(
        "/world/verify",
        json={"visitor": VISITOR, "proof": {**A_PROOF, "action": "claim-airdrop"}},
    )
    assert r.status_code == 502
    assert asked == []


def test_world_answering_for_another_action_is_refused(live, monkeypatch):
    world_says(monkeypatch, {**verified(), "action": "claim-airdrop"})
    r = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    assert r.status_code == 502


def test_a_short_nullifier_is_padded_the_way_world_pads_it(live, monkeypatch):
    """Signed as padded and reported as padded — never one value each."""
    world_says(monkeypatch, verified(nullifier="0x" + "ab" * 31))
    body = client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).json()
    assert body["nullifier_hash"] == "0x00" + "ab" * 31
    assert body["typed_data"]["message"]["nullifierHash"] == body["nullifier_hash"]


def test_a_nullifier_that_is_not_hex_is_a_502_not_a_crash(live, monkeypatch):
    world_says(monkeypatch, verified(nullifier="not-a-nullifier"))
    r = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    assert r.status_code == 502


def test_a_verified_human_gets_an_attestation(live, monkeypatch):
    world_says(monkeypatch, verified())
    body = client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).json()

    assert body["visitor"] == VISITOR
    assert body["nullifier_hash"] == NULLIFIER
    assert len(body["signature"]) == 132


def test_a_proof_world_rejects_is_not_attested(live, monkeypatch):
    """The failure that matters: signing anyway would mint a verified human."""
    world_says(monkeypatch, {"success": False, "detail": "invalid proof"}, status=400)
    r = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    assert r.status_code == 502
    assert "invalid proof" in r.json()["detail"]


def test_success_without_a_nullifier_is_refused(live, monkeypatch):
    """The nullifier is the entire answer. Signing over nothing is worse than
    failing, because the attestation would look valid on chain."""
    world_says(monkeypatch, {"success": True})
    assert client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).status_code == 502


def test_world_being_unreachable_is_a_502_not_a_signature(live, monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", boom)
    assert client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).status_code == 502


# --- one human, one wallet --------------------------------------------------


def test_the_same_human_cannot_collect_a_second_wallet(live, monkeypatch):
    """The attack World exists to stop, rebuilt through our own endpoint."""
    world_says(monkeypatch, verified())
    assert client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).status_code == 200

    r = client.post("/world/verify", json={"visitor": OTHER, "proof": A_PROOF})
    assert r.status_code == 409
    assert "already verified" in r.json()["detail"]


def test_the_same_wallet_can_retry(live, monkeypatch):
    """A dropped connection should not lock somebody out of their own account."""
    world_says(monkeypatch, verified())
    first = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    second = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    assert first.status_code == 200
    assert second.status_code == 200


def test_a_different_human_is_not_blocked(live, monkeypatch):
    world_says(monkeypatch, verified())
    client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})

    world_says(monkeypatch, verified(nullifier="0x" + "cd" * 32))
    assert client.post(
        "/world/verify", json={"visitor": OTHER, "proof": A_PROOF}
    ).status_code == 200


# --- the signature itself ---------------------------------------------------


def test_the_attestation_expires_in_minutes_not_hours(live, monkeypatch):
    world_says(monkeypatch, verified())
    body = client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).json()
    remaining = body["expiry"] - time.time()
    assert 0 < remaining <= get_config().attestation_ttl_seconds


def test_the_signature_recovers_to_the_attester(live, monkeypatch):
    world_says(monkeypatch, verified())
    body = client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).json()

    signable = encode_typed_data(full_message=body["typed_data"])
    assert Account.recover_message(signable, signature=body["signature"]) == ATTESTER


def test_the_digest_matches_what_the_contract_will_compute(live, monkeypatch):
    """The contract between us and VisitRegistry, checked rather than assumed.

    `_hashTypedDataV4` reproduced by hand. If Sebastián's struct ever drifts
    from ours, `ECDSA.recover` returns some other address and every attestation
    silently stops verifying — this is the test that catches it here instead.
    """
    world_says(monkeypatch, verified())
    body = client.post(
        "/world/verify", json={"visitor": VISITOR, "proof": A_PROOF}
    ).json()
    m = body["typed_data"]["message"]

    typehash = Web3.keccak(
        text="WorldAttestation(address visitor,bytes32 nullifierHash,uint64 expiry)"
    )
    struct_hash = Web3.keccak(
        encode(
            ["bytes32", "address", "bytes32", "uint64"],
            [
                typehash,
                Web3.to_checksum_address(m["visitor"]),
                bytes.fromhex(m["nullifierHash"][2:]),
                m["expiry"],
            ],
        )
    )
    domain = Web3.keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                Web3.keccak(
                    text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
                ),
                Web3.keccak(text="ZoneGo"),
                Web3.keccak(text="1"),
                get_config().chain_id,
                Web3.to_checksum_address(REGISTRY),
            ],
        )
    )
    solidity_digest = Web3.keccak(b"\x19\x01" + domain + struct_hash)

    signable = encode_typed_data(full_message=body["typed_data"])
    wallet_digest = Web3.keccak(b"\x19\x01" + signable.header + signable.body)

    assert solidity_digest == wallet_digest


def test_the_attester_address_is_published(live):
    """Anyone can check the address the contract trusts is the one signing."""
    assert client.get("/world/attester").json()["address"] == ATTESTER


# --- the guards -------------------------------------------------------------


def test_mock_mode_refuses_rather_than_faking_a_signature(monkeypatch):
    """There is no honest sample of a signature: a fake one either fails on
    chain, or worse, does not."""
    monkeypatch.setattr(get_config(), "mock_mode", True)
    r = client.post("/world/verify", json={"visitor": VISITOR, "proof": A_PROOF})
    assert r.status_code == 501


def test_a_missing_attester_key_fails_loudly(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(get_config(), "attester_private_key", "")
    assert client.get("/world/attester").status_code == 501


def test_a_malformed_visitor_never_reaches_world():
    assert client.post(
        "/world/verify", json={"visitor": "0x1", "proof": A_PROOF}
    ).status_code == 422


# --- the selfie you do not have to repeat -----------------------------------
#
# Selfie Check is not what the contract burns — our signature is. Someone who
# claimed last week already wrote their nullifier into VisitRegistry, where it
# cannot move to another wallet, so signing again restates a public fact rather
# than vouching for a new one. These guard the fence around that.


def standing_is(monkeypatch, value):
    from api import subgraph

    def fake(visitor):
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(subgraph, "visitor_standing", fake)


def test_a_recent_visitor_is_attested_without_another_selfie(live, monkeypatch):
    standing_is(monkeypatch, (NULLIFIER, int(time.time()) - 3 * 86_400))

    r = client.get(f"/world/attestation/{VISITOR}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visitor"] == VISITOR
    assert body["nullifier_hash"] == NULLIFIER
    assert body["expiry"] > int(time.time())


def test_a_wallet_the_chain_never_saw_still_needs_the_selfie(live, monkeypatch):
    standing_is(monkeypatch, None)
    assert client.get(f"/world/attestation/{OTHER}").status_code == 404


def test_a_visit_older_than_the_window_needs_the_selfie_again(live, monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "world_reverification_days", 15)
    standing_is(monkeypatch, (NULLIFIER, int(time.time()) - 16 * 86_400))

    r = client.get(f"/world/attestation/{VISITOR}")
    assert r.status_code == 404
    assert "15 days" in r.json()["detail"]


def test_an_unreachable_index_is_not_read_as_never_verified(live, monkeypatch):
    """502, not 404.

    "We could not ask" and "they have never verified" send the frontend down
    different paths, and only one of them should cost somebody a selfie.
    """
    from api import subgraph

    standing_is(monkeypatch, subgraph.SubgraphError("studio is down"))
    assert client.get(f"/world/attestation/{VISITOR}").status_code == 502


def test_a_malformed_address_is_refused_before_asking_anything(live, monkeypatch):
    assert client.get("/world/attestation/not-an-address").status_code == 422


def test_mock_mode_refuses_rather_than_inventing_a_signature(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", True)
    assert client.get(f"/world/attestation/{VISITOR}").status_code == 501
