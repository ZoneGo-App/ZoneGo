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

# `geohash` is a string until Sebastian settles bytes12 vs string in
# schema/events.md. If it becomes bytes12, only this table and the payload
# builder change — callers stay the same.
VISIT_TYPE = [
    {"name": "campaignId", "type": "uint256"},
    {"name": "visitor", "type": "address"},
    {"name": "nonce", "type": "uint256"},
    {"name": "expiry", "type": "uint64"},
    {"name": "geohash", "type": "string"},
]


def new_nonce() -> int:
    """Single-use nonce. The contract records it so a photographed QR dies."""
    return secrets.randbits(64)


def build_payload(
    *,
    campaign_id: int,
    visitor: str,
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
            "Visit": VISIT_TYPE,
        },
        "primaryType": "Visit",
        "domain": {
            "name": "ZoneGo",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": {
            "campaignId": campaign_id,
            "visitor": visitor,
            "nonce": nonce,
            "expiry": expiry,
            "geohash": geohash,
        },
    }
