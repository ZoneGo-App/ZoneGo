"""Signing the request that lets IDKit open, with a key only the backend holds.

World ID 4.0 refuses a proof request its relying party has not signed. The
widget cannot sign for itself — the key would have to ship to every browser,
and anybody holding it could open requests in ZoneGo's name — so the frontend
asks this service for a signed context first and hands it to IDKit untouched.

The message and its encoding are World's, not ours, and a single byte out of
place fails every request with nothing but a refusal to show for it. So this
does exactly what `compute_rp_signature` does in World's own implementation
(worldcoin/idkit, rust/core/src/rp_signature.rs), and the tests pin it to the
two vectors World publishes:

    version(1) || nonce(32) || created_at(8, big-endian)
               || expires_at(8, big-endian) || action?(32)

signed with the EIP-191 prefix, as a recoverable 65-byte signature.
"""

import secrets
import string
import time
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

from api.config import get_config

VERSION = b"\x01"


class RpSignatureError(RuntimeError):
    """Not configured, or the key will not sign."""


@dataclass(frozen=True)
class RpContext:
    rp_id: str
    nonce: str
    created_at: int
    expires_at: int
    signature: str


def hash_to_field(data: bytes) -> bytes:
    """keccak256 shifted right by one byte, so the result fits the field.

    World's `FieldElement::from_arbitrary_raw_bytes`, and how both the nonce and
    the action enter the message: a raw 32-byte hash can exceed the field
    modulus, a value one byte shorter never can.
    """
    return (int.from_bytes(keccak(data), "big") >> 8).to_bytes(32, "big")


def message(
    *, nonce: bytes, created_at: int, expires_at: int, action: str | None
) -> bytes:
    """49 bytes without an action, 81 with one."""
    msg = VERSION + nonce + created_at.to_bytes(8, "big") + expires_at.to_bytes(8, "big")
    if action is not None:
        msg += hash_to_field(action.encode("utf-8"))
    return msg


def _clean(key: str) -> str:
    """What a copy-paste leaves around a value: spaces, newlines, quotes.

    A dashboard field keeps whatever was pasted into it, and a key with a
    trailing newline is indistinguishable from a wrong key when all the error
    says is "invalid" — so trim it rather than make somebody guess.
    """
    return key.strip().strip('"').strip("'").strip()


def _describe(raw: str, clean: str) -> str:
    """The shape of a key, never the key.

    This reaches an HTTP response, and the length and whether the characters
    are hex give away nothing worth protecting — while being exactly what
    tells a wrong paste from a wrong key on the first try.
    """
    body = clean[2:] if clean.lower().startswith("0x") else clean
    digits = (
        "hex digits"
        if body and all(character in string.hexdigits for character in body)
        else "not all hex digits"
    )
    prefix = "with 0x" if clean.lower().startswith("0x") else "without 0x"
    trimmed = ", and had whitespace or quotes around it" if clean != raw else ""
    return f"{len(body)} characters {prefix}, {digits}{trimmed}"


def sign(
    *,
    signing_key: str,
    nonce: bytes,
    created_at: int,
    expires_at: int,
    action: str | None,
) -> str:
    """The deterministic half, kept apart so World's vectors can be fed in."""
    key = _clean(signing_key)
    try:
        signer = Account.from_key(key)
    except Exception:  # noqa: BLE001 — every parse failure means the same thing
        # `from None`: the underlying error can quote the key it choked on, and
        # this message reaches an HTTP response.
        raise RpSignatureError(
            "WORLD_RP_SIGNING_KEY is not a 32-byte hex key: "
            f"{_describe(signing_key, key)}. World's key is 64 hex digits, "
            "with or without a 0x prefix."
        ) from None

    signable = encode_defunct(
        primitive=message(
            nonce=nonce, created_at=created_at, expires_at=expires_at, action=action
        )
    )
    return "0x" + signer.sign_message(signable).signature.hex().removeprefix("0x")


def rp_context() -> RpContext:
    """A freshly signed context for one IDKit request."""
    config = get_config()
    if not config.world_rp_signing_key.strip():
        raise RpSignatureError("WORLD_RP_SIGNING_KEY is not set")
    if not config.world_rp_id:
        raise RpSignatureError("WORLD_RP_ID is not set")

    created_at = int(time.time())
    expires_at = created_at + config.world_rp_request_ttl_seconds
    # Random, then pulled into the field — the same two steps World takes, so
    # the nonce handed out is exactly the one inside the signed message.
    nonce = hash_to_field(secrets.token_bytes(32))

    return RpContext(
        rp_id=config.world_rp_id,
        nonce="0x" + nonce.hex(),
        created_at=created_at,
        expires_at=expires_at,
        # The action is signed in, so a widget opened with any other action is
        # a request World refuses — the same string has to be in the portal,
        # in IDKit and here.
        signature=sign(
            signing_key=config.world_rp_signing_key,
            nonce=nonce,
            created_at=created_at,
            expires_at=expires_at,
            action=config.world_action or None,
        ),
    )
