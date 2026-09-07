"""The payload a merchant signs to open a visit.

The server assembles it and hands it back. It does not sign, and it holds no
merchant key — the merchant's own wallet signs, and the contract checks that
signature on chain. If this service disappeared, a merchant could build the
same payload themselves and nothing about the system would change.
"""

from fastapi import APIRouter, HTTPException

from api.config import get_config
from api.eip712 import build_payload
from api.mock_data import CAMPAIGNS
from api.schemas import QrSignRequest, QrSignResponse

router = APIRouter(prefix="/qr", tags=["qr"])


def _find_campaign(campaign_id: int):
    config = get_config()
    if not config.mock_mode:
        raise HTTPException(501, "Chain reads not connected yet")
    for campaign in CAMPAIGNS:
        if campaign.campaign_id == campaign_id:
            return campaign
    raise HTTPException(404, "Campaign not found")


@router.post("/sign", response_model=QrSignResponse)
def sign(req: QrSignRequest):
    campaign = _find_campaign(req.campaign_id)
    if not campaign.active:
        raise HTTPException(409, "Campaign is not active")
    if campaign.balance < campaign.reward_per_visit:
        # Better to refuse here than to let someone walk to the store and have
        # the claim revert once they are standing at the counter.
        raise HTTPException(409, "Campaign is out of funds")

    config = get_config()
    payload = build_payload(
        campaign_id=campaign.campaign_id,
        geohash=campaign.geohash,
        chain_id=config.chain_id,
        verifying_contract=config.visit_registry_address,
        signature_ttl_seconds=config.signature_ttl_seconds,
    )

    return QrSignResponse(
        typed_data=payload,
        nonce=payload["message"]["nonce"],
        expiry=payload["message"]["expiry"],
        rotate_after_seconds=config.qr_rotation_seconds,
    )
