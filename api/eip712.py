"""The EIP-712 payload a merchant signs to prove someone walked in.

The server assembles this payload. It never signs it — the merchant's own
wallet does, and the contract verifies that signature on chain. That split is
the whole reason ZoneGo needs a blockchain: if the server signed, the server
would be the authority and the merchant would have to trust us.

The struct mirrors `VisitSig` in the contract. Any change here has to land in
`schema/events.md` and be agreed with Sebastian first.
"""

import secrets
import time

# This mirrors VISIT_TYPEHASH in VisitRegistry.sol, character for character:
#
#   "VisitSig(uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash,address visitor)"
#
# A single difference — a renamed field, a reordered one, string instead of
# bytes32 — produces a different hash, the contract rejects the merchant's
# signature, and nobody gets paid. Change this only alongside the contract.
#
# `visitor` is signed rather than passed alongside. Without it inside the
# struct, anyone holding the signature could call claim() with their own
# address and take the reward — and the signature is on a screen in a shop,
# so "anyone holding it" means anyone who walked past.
STRUCT_NAME = "VisitSig"

VISIT_TYPE = [
    {"name": "campaignId", "type": "uint256"},
    {"name": "nonce", "type": "uint256"},
    {"name": "expiry", "type": "uint64"},
    {"name": "geohash", "type": "bytes32"},
    {"name": "visitor", "type": "address"},
]


def geohash_to_bytes32(geohash: str) -> str:
    """ASCII geohash right-padded with zeros, the way Solidity reads bytes32."""
    raw = geohash.encode("ascii")
    if len(raw) > 32:
        raise ValueError("geohash does not fit in bytes32")
    return "0x" + raw.hex().ljust(64, "0")


def geohash_from_bytes32(raw: str | bytes) -> str:
    """The inverse, for values read back off the chain.

    The subgraph hands these over as a hex string and an `eth_call` as raw
    bytes, so both forms arrive here rather than being unpacked twice.
    """
    if isinstance(raw, str):
        raw = bytes.fromhex(raw.removeprefix("0x"))
    return raw.rstrip(b"\x00").decode("ascii")


def new_nonce() -> int:
    """Single-use nonce. The contract records it so a photographed QR dies."""
    return secrets.randbits(64)


def _js_safe(value: int) -> str:
    """A uint256 as a decimal string, because JSON numbers are not integers.

    A 64-bit nonce is past 2**53 almost every time, and that is where a
    JavaScript number stops being exact. `JSON.parse` would round it silently —
    no error, no warning — and the wallet would sign a nonce the contract never
    issued. Every claim would revert and nothing in the frontend would say why.

    A string survives the trip whole, and viem and ethers both take one wherever
    a uint256 is expected. Solidity never sees this: the wallet turns it back
    into a number before hashing.
    """
    return str(value)


def build_payload(
    *,
    campaign_id: int,
    geohash: str,
    visitor: str,
    chain_id: int,
    verifying_contract: str,
    signature_ttl_seconds: int,
    nonce: int | None = None,
) -> dict:
    """The document the merchant's wallet signs, for one visitor.

    `visitor` is required because it is inside the signed struct: a payload is
    good for one person, not for whoever reaches the contract first. That means
    the merchant cannot pre-sign a QR and leave it on screen for the room — the
    address has to be known before signing.
    """
    nonce = new_nonce() if nonce is None else nonce
    expiry = int(time.time()) + signature_ttl_seconds

    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            STRUCT_NAME: VISIT_TYPE,
        },
        "primaryType": STRUCT_NAME,
        "domain": {
            "name": "ZoneGo",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": {
            "campaignId": campaign_id,
            # A string on purpose — see `_js_safe`. The other two numbers here
            # are small enough to survive JSON: a campaign id counts stores, and
            # an expiry is seconds since 1970.
            "nonce": _js_safe(nonce),
            "expiry": expiry,
            "geohash": geohash_to_bytes32(geohash),
            "visitor": visitor,
        },
    }
