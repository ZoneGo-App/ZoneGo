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
#   "VisitSig(uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash)"
#
# A single difference — a renamed field, a reordered one, string instead of
# bytes32 — produces a different hash, the contract rejects the merchant's
# signature, and nobody gets paid. Change this only alongside the contract.
STRUCT_NAME = "VisitSig"

VISIT_TYPE = [
    {"name": "campaignId", "type": "uint256"},
    {"name": "nonce", "type": "uint256"},
    {"name": "expiry", "type": "uint64"},
    {"name": "geohash", "type": "bytes32"},
]


def geohash_to_bytes32(geohash: str) -> str:
    """ASCII geohash right-padded with zeros, the way Solidity reads bytes32."""
    raw = geohash.encode("ascii")
    if len(raw) > 32:
        raise ValueError("geohash does not fit in bytes32")
    return "0x" + raw.hex().ljust(64, "0")


def new_nonce() -> int:
    """Single-use nonce. The contract records it so a photographed QR dies."""
    return secrets.randbits(64)


def build_payload(
    *,
    campaign_id: int,
    geohash: str,
    chain_id: int,
    verifying_contract: str,
    signature_ttl_seconds: int,
    nonce: int | None = None,
) -> dict:
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
            "nonce": nonce,
            "expiry": expiry,
            "geohash": geohash_to_bytes32(geohash),
        },
    }
