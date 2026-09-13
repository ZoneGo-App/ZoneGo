"""Failures the browser has to be able to read.

A claim on the live deployment answered 500 on every attempt, and the frontend
saw only "Failed to fetch": Starlette's own 500 is built outside the CORS
middleware, so it left without CORS headers and the browser threw it away. The
cause underneath was a relay setting that failed to parse outside the relay's
error handling, so it was never turned into the 502 the frontend knows how to
show. These cover both halves.
"""

import time

import pytest
from fastapi.testclient import TestClient

from api import relay
from api.config import Config, get_config
from api.eip712 import geohash_to_bytes32
from api.main import app
from api.routers import visits

# The origin CORS allows under the pinned test settings.
ORIGIN = "http://localhost:3000"
VISITOR = "0x" + "a1" * 20
REAL_LOOKING_KEY = "0x" + "11" * 32


def a_claim_body():
    now = int(time.time())
    return {
        "campaign_id": 1,
        "nonce": "123456789",
        "expiry": now + 80,
        "geohash": geohash_to_bytes32("dr5rsked"),
        "signature": "0x" + "b2" * 65,
        "visitor": VISITOR,
        "attestation": {
            "visitor": VISITOR,
            "nullifier_hash": "0x" + "c3" * 32,
            "expiry": now + 3000,
            "signature": "0x" + "d4" * 65,
            "typed_data": {},
        },
    }


# --- an unexpected error is still a response the browser can read ----------


def test_an_unexpected_error_keeps_its_cors_headers(monkeypatch):
    """The bug, reduced to its mechanism: any exception nobody anticipated."""

    def explode(campaign_id):
        raise RuntimeError("something nobody planned for")

    monkeypatch.setattr(visits, "resolve_campaign", explode)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/visits/claim", json=a_claim_body(), headers={"Origin": ORIGIN})

    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert "detail" in r.json()


def test_the_500_body_does_not_repeat_the_exception(monkeypatch):
    """An unexpected error is the one whose message nobody checked is safe."""

    def explode(campaign_id):
        raise RuntimeError("secret-looking internal detail 0xdeadbeef")

    monkeypatch.setattr(visits, "resolve_campaign", explode)
    client = TestClient(app, raise_server_exceptions=False)

    body = client.post("/visits/claim", json=a_claim_body(), headers={"Origin": ORIGIN}).text
    assert "0xdeadbeef" not in body
    assert "RuntimeError" not in body


def test_the_traceback_goes_to_the_log(monkeypatch, caplog):
    def explode(campaign_id):
        raise RuntimeError("find me in the log")

    monkeypatch.setattr(visits, "resolve_campaign", explode)
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="zonego"):
        client.post("/visits/claim", json=a_claim_body(), headers={"Origin": ORIGIN})

    assert any("unhandled_error" in r.getMessage() and r.exc_info for r in caplog.records)


# --- the relay's own settings fail as relay errors, not crashes -------------


@pytest.fixture
def relay_wired(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "rpc_url", "https://example.test/rpc")
    monkeypatch.setattr(config, "visit_registry_address", "0xed168b6B9c96f59Be1AD3866F24e8851D3Afca4e")
    monkeypatch.setattr(config, "relay_private_key", REAL_LOOKING_KEY)
    return config


def a_relay_claim():
    body = a_claim_body()
    a = body["attestation"]
    return relay.Claim(
        campaign_id=1, nonce=1, expiry=body["expiry"], geohash=body["geohash"],
        signature=body["signature"], visitor=VISITOR, nullifier_hash=a["nullifier_hash"],
        attestation_expiry=a["expiry"], attestation_signature=a["signature"],
    )


def test_a_malformed_relay_key_is_a_relay_error_that_does_not_show_the_key(relay_wired, monkeypatch):
    broken = "0x" + "11" * 31 + "zz"
    monkeypatch.setattr(relay_wired, "relay_private_key", broken)

    with pytest.raises(relay.RelayError) as caught:
        relay.send_claim(a_relay_claim())

    assert "RELAY_PRIVATE_KEY" in str(caught.value)
    assert broken not in str(caught.value)
    assert "11" * 31 not in str(caught.value)


def test_a_malformed_registry_address_is_a_relay_error(relay_wired, monkeypatch):
    monkeypatch.setattr(relay_wired, "visit_registry_address", "0xnot-an-address")
    with pytest.raises(relay.RelayError, match="VISIT_REGISTRY_ADDRESS"):
        relay.send_claim(a_relay_claim())


def test_a_node_that_refuses_the_http_request_is_a_relay_error(relay_wired, monkeypatch):
    """A rate limit or 5xx from the RPC arrives as a requests error, not a Web3Exception."""
    import requests

    def refuse(self, method, params):
        raise requests.exceptions.HTTPError("429 Client Error: Too Many Requests for url: https://example.test/rpc")

    monkeypatch.setattr("web3.providers.rpc.HTTPProvider.make_request", refuse)
    with pytest.raises(relay.RelayError) as caught:
        relay.send_claim(a_relay_claim())
    assert "HTTPError" in str(caught.value)
    assert "example.test" not in str(caught.value)


# --- pasted values, and what /ready says about them -------------------------


def test_a_key_pasted_with_a_newline_or_quotes_is_trimmed():
    for dirty in (REAL_LOOKING_KEY + "\n", f'"{REAL_LOOKING_KEY}"', f"  {REAL_LOOKING_KEY} \r\n"):
        assert Config(relay_private_key=dirty).relay_private_key == REAL_LOOKING_KEY


def test_ready_calls_an_unparseable_key_invalid_not_configured(monkeypatch):
    """The check that would have caught this before anyone tried to claim."""
    from api.routers import health

    config = get_config()
    monkeypatch.setattr(config, "mock_mode", False)
    monkeypatch.setattr(health, "_subgraph", lambda config: "ok")
    monkeypatch.setattr(health, "_node", lambda config: "ok")
    monkeypatch.setattr(config, "relay_private_key", "0x" + "11" * 31 + "zz")
    monkeypatch.setattr(config, "attester_private_key", REAL_LOOKING_KEY)
    monkeypatch.setattr(config, "visit_registry_address", "0xnot-an-address")

    checks = TestClient(app).get("/ready").json()["checks"]
    assert checks["relay_key"] == "invalid"
    assert checks["attester_key"] == "configured"
    assert checks["operator_key"] == "missing"
    assert checks["registry_address"] == "invalid"
