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

from api import observability, relay
from api.config import get_config
from api.eip712 import geohash_to_bytes32
from api.routers.campaigns import resolve as resolve_campaign
from api.schemas import ClaimRequest, ClaimResponse

router = APIRouter(prefix="/visits", tags=["visits"])


def _refuse(status: int, reason: str, message: str, req: ClaimRequest):
    """Refuse a claim, and leave a record of why.

    Every path out of this endpoint that is not a payment goes through here, so
    the counters and the log agree with each other by construction. A merchant
    asking why nobody got paid this afternoon gets an answer grouped by reason
    instead of a scroll of prose.
    """
    observability.rejected(
        reason,
        campaign_id=req.campaign_id,
        visitor=req.visitor,
        nonce=req.nonce,
    )
    raise HTTPException(status, message)


@router.post("/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    if req.expiry <= int(time.time()):
        # The QR redraws every 30 seconds and a signature lives 90. Past that,
        # a photographed screen is worthless — which is the point.
        _refuse(410, "signature_expired", "Signature expired, scan the QR again", req)

    # The same view the caller read off GET /campaigns/{id}: the vault for the
    # balance and the geohash, the index for the rest. Validating against the
    # sample data instead would refuse every real campaign once the contracts
    # are live, and pass claims for stores that no longer have funds.
    campaign = resolve_campaign(req.campaign_id)
    if not campaign.active:
        _refuse(409, "campaign_inactive", "Campaign is not active", req)
    if campaign.balance < campaign.reward_per_visit:
        _refuse(409, "campaign_out_of_funds", "Campaign is out of funds", req)
    if req.geohash.lower() != geohash_to_bytes32(campaign.geohash).lower():
        # A signature carrying another store's geohash was never going to pass
        # the contract. Catching it costs nothing; relaying it costs gas.
        _refuse(
            409,
            "geohash_mismatch",
            "Geohash does not belong to this campaign",
            req,
        )

    config = get_config()
    if not config.mock_mode:
        attestation = req.attestation
        if attestation is None:
            # Without it there is no nullifier, and a zero would put every
            # visitor in one weekly bucket — the second person to claim
            # anywhere would be paid 50% of a reward that was their first.
            _refuse(
                400,
                "missing_attestation",
                "attestation is required: call POST /world/verify first",
                req,
            )
        if attestation.expiry <= int(time.time()):
            # Its own clock, separate from the QR's. Two minutes from the World
            # session that produced it, so a stale one means verify again
            # rather than scan again.
            _refuse(
                410,
                "attestation_expired",
                "World attestation expired, verify again",
                req,
            )
        if attestation.visitor.lower() != req.visitor.lower():
            # The contract refuses this too. Catching it here saves the gas of
            # finding out on chain.
            _refuse(
                400,
                "attestation_visitor_mismatch",
                "Attestation names a different visitor",
                req,
            )
        if (
            req.nullifier_hash
            and req.nullifier_hash.lower() != attestation.nullifier_hash.lower()
        ):
            # Two answers to one question. The contract reads the nullifier out
            # of the attestation and ignores the loose field, so a caller
            # sending both is confused about which one counts — say so instead
            # of quietly preferring either.
            _refuse(
                400,
                "nullifier_disagrees_with_attestation",
                "nullifier_hash does not match the attestation",
                req,
            )

        try:
            tx_hash = relay.send_claim(
                relay.Claim(
                    campaign_id=req.campaign_id,
                    nonce=req.nonce,
                    expiry=req.expiry,
                    geohash=req.geohash,
                    signature=req.signature,
                    visitor=req.visitor,
                    nullifier_hash=attestation.nullifier_hash,
                    attestation_expiry=attestation.expiry,
                    attestation_signature=attestation.signature,
                )
            )
        except relay.RelayError as exc:
            # The one rejection that already cost something: we reached the
            # node and it refused, or we could not reach it at all. Worth
            # separating from the checks above, which cost nothing.
            observability.rejected(
                "relay_failed",
                campaign_id=req.campaign_id,
                visitor=req.visitor,
                error=str(exc),
            )
            raise HTTPException(502, f"Relay failed: {exc}") from exc

        return ClaimResponse(tx_hash=tx_hash, status="submitted", relayed=True)

    # Deterministic stand-in for a transaction hash: the same claim always
    # yields the same value, so the frontend can be tested against it.
    digest = hashlib.sha256(
        f"{req.campaign_id}:{req.nonce}:{req.visitor}".encode()
    ).hexdigest()

    return ClaimResponse(tx_hash=f"0x{digest}", status="simulated", relayed=True)
