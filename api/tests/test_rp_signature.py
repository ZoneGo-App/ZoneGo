"""The request signature World checks before IDKit will open.

Byte for byte or nothing: World refuses a request whose signature does not
recover to the relying party's key, and says little more than no. So the core
of this file is World's own published vectors, reproduced exactly.
"""

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

from api import rp_signature
from api.config import get_config
from api.main import app

client = TestClient(app)

# World's test inputs and outputs, verbatim from
# https://docs.world.org/world-id/idkit/signatures.md
WORLD_KEY = "0x" + "ab" * 32
WORLD_RANDOM = bytes(range(32))
CREATED_AT = 1700000000
EXPIRES_AT = 1700000300
WORLD_NONCE = "0x008ae1aa597fa146ebd3aa2ceddf360668dea5e526567e92b0321816a4e895bd"
WORLD_SIGNATURE_NO_ACTION = (
    "0x14f693175773aed912852a601e9c0fd30f2afe2738d31388316232ce6f64ae9e"
    "4edbfb19d81c4229ba9c9fca78ede4b28956b7ba4415f08d957cbc1b3bdaa4021b"
)
WORLD_SIGNATURE_TEST_ACTION = (
    "0x05594adb6c1495768a38d523d7d6ee6356b2c31231919198794ed022ade7d08f"
    "73753f83bd167067d99c9b969d28e9222315837c66af25867b041273a6d5056f1b"
)

# A key that exists only here.
RP_KEY = "0x" + "22" * 32
RP_SIGNER = Account.from_key(RP_KEY).address


def test_the_nonce_matches_worlds_vector():
    assert "0x" + rp_signature.hash_to_field(WORLD_RANDOM).hex() == WORLD_NONCE


@pytest.mark.parametrize(
    "action, expected, length",
    [
        (None, WORLD_SIGNATURE_NO_ACTION, 49),
        ("test-action", WORLD_SIGNATURE_TEST_ACTION, 81),
    ],
)
def test_the_signature_matches_worlds_published_vectors(action, expected, length):
    """If this fails, every IDKit request in production fails with it."""
    nonce = rp_signature.hash_to_field(WORLD_RANDOM)
    message = rp_signature.message(
        nonce=nonce, created_at=CREATED_AT, expires_at=EXPIRES_AT, action=action
    )
    assert len(message) == length
    assert (
        rp_signature.sign(
            signing_key=WORLD_KEY,
            nonce=nonce,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
            action=action,
        )
        == expected
    )


@pytest.fixture
def configured(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "world_app_id", "app_test")
    monkeypatch.setattr(config, "world_rp_id", "rp_test")
    monkeypatch.setattr(config, "world_rp_signing_key", RP_KEY)
    monkeypatch.setattr(config, "world_action", "verify-visitor")


def signer_of(context: dict, action: str) -> str:
    message = rp_signature.message(
        nonce=bytes.fromhex(context["nonce"].removeprefix("0x")),
        created_at=context["created_at"],
        expires_at=context["expires_at"],
        action=action,
    )
    return Account.recover_message(
        encode_defunct(primitive=message), signature=context["signature"]
    )


def test_the_frontend_gets_everything_idkit_needs(configured):
    r = client.get("/world/rp-context")
    assert r.status_code == 200
    body = r.json()
    assert body["app_id"] == "app_test"
    assert body["action"] == "verify-visitor"
    context = body["rp_context"]
    assert context["rp_id"] == "rp_test"
    assert (
        context["expires_at"] - context["created_at"]
        == get_config().world_rp_request_ttl_seconds
    )


def test_the_signature_recovers_to_our_key_over_our_action(configured):
    context = client.get("/world/rp-context").json()["rp_context"]
    assert signer_of(context, "verify-visitor") == RP_SIGNER


def test_a_widget_opened_with_another_action_would_not_verify(configured):
    """The action is inside the signature, so it cannot be swapped client-side."""
    context = client.get("/world/rp-context").json()["rp_context"]
    assert signer_of(context, "some-other-action") != RP_SIGNER


def test_every_request_gets_its_own_nonce(configured):
    """World treats nonces as single use."""
    first = client.get("/world/rp-context").json()["rp_context"]["nonce"]
    second = client.get("/world/rp-context").json()["rp_context"]["nonce"]
    assert first != second


def test_nothing_is_allowed_to_cache_it(configured):
    """A cached context replays a nonce World has already seen."""
    assert client.get("/world/rp-context").headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "missing", ["world_rp_signing_key", "world_rp_id", "world_app_id"]
)
def test_a_missing_setting_is_501_not_a_signature_that_fails_later(
    configured, monkeypatch, missing
):
    monkeypatch.setattr(get_config(), missing, "")
    assert client.get("/world/rp-context").status_code == 501


def test_a_malformed_key_is_never_repeated_back(configured, monkeypatch):
    monkeypatch.setattr(get_config(), "world_rp_signing_key", "0x" + "zq" * 32)
    r = client.get("/world/rp-context")
    assert r.status_code == 501
    assert "zq" not in r.text


@pytest.mark.parametrize(
    "pasted",
    [
        "  " + WORLD_KEY + "  ",
        WORLD_KEY + "\n",
        '"' + WORLD_KEY + '"',
        "'" + WORLD_KEY + "'\n",
    ],
)
def test_a_key_pasted_with_spaces_or_quotes_still_signs(pasted):
    """A dashboard field keeps whatever was pasted into it, and a trailing
    newline is not a different key."""
    nonce = rp_signature.hash_to_field(WORLD_RANDOM)
    assert (
        rp_signature.sign(
            signing_key=pasted,
            nonce=nonce,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
            action=None,
        )
        == WORLD_SIGNATURE_NO_ACTION
    )


def test_the_error_describes_the_shape_so_it_can_be_fixed_in_one_try(
    configured, monkeypatch
):
    """"Invalid" leaves you guessing between a wrong paste and a wrong key."""
    monkeypatch.setattr(get_config(), "world_rp_signing_key", "0x" + "ab" * 31)
    detail = client.get("/world/rp-context").json()["detail"]
    assert "62 characters" in detail
    assert "hex digits" in detail
    assert "64 hex digits" in detail


def test_the_error_says_when_something_was_wrapped_around_the_key(
    configured, monkeypatch
):
    monkeypatch.setattr(get_config(), "world_rp_signing_key", '"0xnothex"\n')
    detail = client.get("/world/rp-context").json()["detail"]
    assert "not all hex digits" in detail
    assert "whitespace or quotes around it" in detail
    assert "nothex" not in detail
