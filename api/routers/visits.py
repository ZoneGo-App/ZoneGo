"""The relay: we pay the gas so the visitor does not need any.

This is a convenience, not an authority. The merchant's signature is what the
contract verifies, and we cannot change a byte of it without the contract
throwing the claim out. If this service went down, the visitor could send the
exact same call themselves and still get paid.

What we do add is a filter: rejecting an expired or malformed claim here costs
nothing, while letting it reach the chain costs gas for a transaction that was
always going to revert.
"""

import hashlib
import time

from fastapi import APIRouter, HTTPException

from api.config import get_config
from api.eip712 import geohash_to_bytes32
from api.routers.campaigns import resolve as resolve_campaign
from api.schemas import ClaimRequest, ClaimResponse

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    if req.expiry <= int(time.time()):
        # The QR redraws every 30 seconds and a signature lives 90. Past that,
        # a photographed screen is worthless — which is the point.
        raise HTTPException(410, "Signature expired, scan the QR again")

    # The same view the caller read off GET /campaigns/{id}: the vault for the
    # balance and the geohash, the index for the rest. Validating against the
    # sample data instead would refuse every real campaign once the contracts
    # are live, and pass claims for stores that no longer have funds.
    campaign = resolve_campaign(req.campaign_id)
    if not campaign.active:
        raise HTTPException(409, "Campaign is not active")
    if campaign.balance < campaign.reward_per_visit:
        raise HTTPException(409, "Campaign is out of funds")
    if req.geohash.lower() != geohash_to_bytes32(campaign.geohash).lower():
        # A signature carrying another store's geohash was never going to pass
        # the contract. Catching it costs nothing; relaying it costs gas.
        raise HTTPException(409, "Geohash does not belong to this campaign")

    config = get_config()
    if not config.mock_mode:
        # Everything above already ran against the real campaign, so only the
        # sending is missing. Waiting on the deployed VisitRegistry address and
        # a key with gas; the call is
        #
        #   claim(VisitSig sig, address visitor, bytes signature, bytes32 nullifierHash)
        #
        # Note `visitor` sits outside the signed struct: whoever sends the
        # transaction picks who gets paid. Until World's proof binds the two,
        # that choice is ours, and it is the question a judge will ask.
        raise HTTPException(501, "Relay not connected to the chain yet")

    # Deterministic stand-in for a transaction hash: the same claim always
    # yields the same value, so the frontend can be tested against it.
    digest = hashlib.sha256(
        f"{req.campaign_id}:{req.nonce}:{req.visitor}".encode()
    ).hexdigest()

    return ClaimResponse(tx_hash=f"0x{digest}", status="simulated", relayed=True)
