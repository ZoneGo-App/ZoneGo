"""A store's own name and description, set by the merchant who owns it.

Every campaign used to reach the map as "Merchant 0xd17c…9db4", because the
vault stores no name. These two routes let a merchant give one — and campaigns,
search and the map pick it up without a redeploy of anything on chain.
"""

import re

from fastapi import APIRouter, HTTPException

from api import profiles
from api.schemas import MerchantProfile, MerchantProfileRequest

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("/profile", response_model=MerchantProfile)
def save_profile(req: MerchantProfileRequest):
    """Save a store's name and description, signed by its wallet.

    401 when the signature is missing its mark — wrong wallet, unreadable, or
    signed too long ago. 409 when a newer profile is already saved, so an old
    signed request cannot be replayed to put back a name the merchant changed.
    """
    try:
        profile = profiles.save(
            wallet=req.wallet,
            name=req.name,
            description=req.description,
            issued_at=req.issued_at,
            signature=req.signature,
        )
    except profiles.ProfileError as exc:
        raise HTTPException(exc.status, str(exc)) from exc

    return MerchantProfile(
        wallet=profile.wallet,
        name=profile.name,
        description=profile.description,
        issued_at=profile.issued_at,
    )


@router.get("/profile/{wallet}", response_model=MerchantProfile)
def read_profile(wallet: str):
    """What a merchant has saved. Lets the form load it back, and a person check it."""
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", wallet):
        raise HTTPException(422, "wallet must be a 0x address")

    profile = profiles.get(wallet)
    if profile is None:
        raise HTTPException(404, "No profile saved for this wallet")

    return MerchantProfile(
        wallet=profile.wallet,
        name=profile.name,
        description=profile.description,
        issued_at=profile.issued_at,
    )
