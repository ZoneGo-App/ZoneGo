"""The bridge between World's cloud and a contract that cannot call it.

Selfie Check has no on-chain proof artifact — the World ID Router takes Orb
credentials only, and the v4 verifier is not on Base. So the chain cannot ask,
and this endpoint answers for it: we put the question to World and sign what
comes back.

The signature is short-lived and names one wallet, so it is worth nothing to
anyone else and worth nothing tomorrow.
"""

from fastapi import APIRouter, HTTPException, Response

from api import rp_signature, world
from api.config import get_config
from api.schemas import (
    WorldAttestation,
    WorldRequest,
    WorldRpContext,
    WorldVerifyRequest,
)

router = APIRouter(prefix="/world", tags=["world"])


@router.get("/rp-context", response_model=WorldRequest)
def request_context(response: Response):
    """What IDKit needs before it will open: our signature over one request.

    World ID 4.0 refuses a request its relying party has not signed, and the key
    cannot live in a browser. So the frontend calls this first, passes
    `rp_context` to IDKit untouched, and opens the widget with the `app_id` and
    `action` returned here.

    Works in mock mode too: signing costs nothing and proves nothing on its
    own — it is the verification afterwards that needs the live path.
    """
    config = get_config()
    if not config.world_app_id:
        raise HTTPException(501, "WORLD_APP_ID is not set")
    try:
        context = rp_signature.rp_context()
    except rp_signature.RpSignatureError as exc:
        raise HTTPException(501, str(exc)) from exc

    # The nonce is single use. A response served again from any cache is a
    # request World refuses, so nothing may keep a copy.
    response.headers["Cache-Control"] = "no-store"
    return WorldRequest(
        app_id=config.world_app_id,
        action=config.world_action,
        rp_context=WorldRpContext(
            rp_id=context.rp_id,
            nonce=context.nonce,
            created_at=context.created_at,
            expires_at=context.expires_at,
            signature=context.signature,
        ),
    )


@router.post("/verify", response_model=WorldAttestation)
def verify(req: WorldVerifyRequest):
    """Check a Selfie Check proof with World and attest the result."""
    config = get_config()
    if config.mock_mode:
        # A signature is the whole product of this endpoint, so there is no
        # honest sample to return: a fake one either fails on chain, or worse,
        # does not. The frontend builds against the live path or not at all.
        raise HTTPException(501, "World verification needs live mode and a key")

    try:
        nullifier = world.verify_with_world(req.proof)
        attestation = world.attest(visitor=req.visitor, nullifier_hash=nullifier)
    except world.NullifierAlreadyBound as exc:
        # 409 rather than 403: nothing is wrong with the request, the person is
        # simply already known under another wallet. Telling them apart is what
        # lets the app say "you already verified" instead of "access denied".
        raise HTTPException(409, str(exc)) from exc
    except world.WorldError as exc:
        raise HTTPException(502, str(exc)) from exc

    return WorldAttestation(
        visitor=attestation.visitor,
        nullifier_hash=attestation.nullifier_hash,
        expiry=attestation.expiry,
        signature=attestation.signature,
        typed_data=attestation.typed_data,
    )


@router.get("/attester")
def attester():
    """The address the contract must trust. Public, and useful to publish.

    Sebastián hardcodes this in `VisitRegistry`; exposing it here means anyone
    can check that the address the contract trusts is the one actually signing,
    without taking our word for it.
    """
    try:
        return {"address": world.attester_address()}
    except world.WorldError as exc:
        raise HTTPException(501, str(exc)) from exc
