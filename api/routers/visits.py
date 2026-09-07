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
from api.mock_data import CAMPAIGNS
from api.schemas import ClaimRequest, ClaimResponse

router = APIRouter(prefix="/visits", tags=["visits"])


def _campaign_or_404(campaign_id: int):
    for campaign in CAMPAIGNS:
        if campaign.campaign_id == campaign_id:
            return campaign
    raise HTTPException(404, "Campaign not found")


@router.post("/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    if req.expiry <= int(time.time()):
        # The QR redraws every 30 seconds and a signature lives 90. Past that,
        # a photographed screen is worthless — which is the point.
        raise HTTPException(410, "Signature expired, scan the QR again")

    campaign = _campaign_or_404(req.campaign_id)
    if not campaign.active:
        raise HTTPException(409, "Campaign is not active")
    if campaign.balance < campaign.reward_per_visit:
        raise HTTPException(409, "Campaign is out of funds")

    config = get_config()
    if not config.mock_mode:
        # Waiting on the deployed VisitRegistry address and its ABI. The call
        # is claim(VisitSig, signature, worldProof) — already fixed in the
        # contract skeleton, so only the sending is missing.
        raise HTTPException(501, "Relay not connected to the chain yet")

    # Deterministic stand-in for a transaction hash: the same claim always
    # yields the same value, so the frontend can be tested against it.
    digest = hashlib.sha256(
        f"{req.campaign_id}:{req.nonce}:{req.visitor}".encode()
    ).hexdigest()

    return ClaimResponse(tx_hash=f"0x{digest}", status="simulated", relayed=True)
