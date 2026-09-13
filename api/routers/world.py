"""The bridge between World's cloud and a contract that cannot call it.

Selfie Check has no on-chain proof artifact — the World ID Router takes Orb
credentials only, and the v4 verifier is not on Base. So the chain cannot ask,
and this endpoint answers for it: we put the question to World and sign what
comes back.

The signature is short-lived and names one wallet, so it is worth nothing to
anyone else and worth nothing tomorrow.
"""

import re
import time

from fastapi import APIRouter, HTTPException, Response

from api import rp_signature, subgraph, world
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


@router.get("/attestation/{visitor}", response_model=WorldAttestation)
def attestation_for(visitor: str):
    """An attestation for somebody the chain has already seen prove themselves.

    Selfie Check is not the thing the contract burns — our signature is. A
    visitor who has claimed before has their nullifier written into
    `VisitRegistry`, where it can never move to another wallet, so issuing them
    a fresh attestation restates a fact anybody can read off the chain rather
    than vouching for something new.

    404 when there is nothing to restate: no visits, or no nullifier yet. That
    is the first-time case, and it goes through Selfie Check. Call this before
    opening IDKit and only open the widget on a 404 — which is what stops us
    asking for a selfie from someone who walked here last week.
    """
    config = get_config()
    if config.mock_mode:
        raise HTTPException(501, "World attestation needs live mode and a key")

    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", visitor):
        raise HTTPException(422, "visitor must be a 0x address")

    try:
        standing = subgraph.visitor_standing(visitor)
    except subgraph.SubgraphError as exc:
        # Not a 404: "we could not ask" and "they have never verified" send the
        # frontend down different paths, and only one of them should cost the
        # visitor a selfie.
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc

    if standing is None:
        raise HTTPException(404, "No verified visit on chain for this wallet yet")

    nullifier_hash, last_visit = standing
    window = config.world_reverification_days * 86_400
    if int(time.time()) - last_visit > window:
        raise HTTPException(
            404,
            f"Last verified visit is older than {config.world_reverification_days} days",
        )

    try:
        attestation = world.attest(visitor=visitor, nullifier_hash=nullifier_hash)
    except world.NullifierAlreadyBound as exc:
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
