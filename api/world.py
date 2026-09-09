"""Selfie Check, and the one place in ZoneGo where the server signs.

Everywhere else the server assembles and the chain decides. The merchant signs
a visit, the contract verifies it, and if this service disappeared a visitor
could still claim. That is the answer to "why does this need a blockchain".

World breaks the pattern, and not by our choice. The World ID Router only
verifies Orb credentials on chain — their documentation says it plainly, the
`groupId` must be 1 — and the v4 verifier is deployed on World Chain rather
than Base. There is no path that lets `VisitRegistry` ask World whether a face
was checked.

So the flow bends: our backend asks World, and then signs an attestation saying
what World answered. The contract trusts that signature. That is a real trust
assumption and it is worth naming, because a judge will find it either way:

    on this one fact, the contract believes us

Everything around it stays as it was. We cannot invent a visit — the merchant's
signature still governs that — and we cannot change a score after the fact,
because the Merkle root is already published. What we could do, if this key
leaked, is mint verified humans. Hence a separate key from the relay, an
attestation that expires in two minutes, and a nullifier that can only ever be
bound to one wallet.
"""

import time
from dataclasses import dataclass

import httpx
from eth_account import Account
from eth_account.messages import encode_typed_data

from api.config import get_config


class WorldError(RuntimeError):
    """World refused the proof, or could not be reached to ask."""


class NullifierAlreadyBound(WorldError):
    """This human already has an attestation for a different wallet.

    The whole point of a nullifier: one person, one identity. Letting the same
    human collect attestations for two addresses would rebuild the wallet farm
    World exists to prevent.
    """


# Mirrors the struct `VisitRegistry` will verify. Same domain as the visit
# signature — EIP712("ZoneGo", "1") — so the contract reuses the machinery it
# already has, and a mismatch here shows up as a recover that returns the wrong
# address rather than as something subtle.
STRUCT_NAME = "WorldAttestation"

ATTESTATION_TYPE = [
    {"name": "visitor", "type": "address"},
    {"name": "nullifierHash", "type": "bytes32"},
    {"name": "expiry", "type": "uint64"},
]


@dataclass(frozen=True)
class Attestation:
    """What we hand the frontend to carry into the claim."""

    visitor: str
    nullifier_hash: str
    expiry: int
    signature: str
    # So the caller can show the same document the contract will hash, and so a
    # test can recover the signer without rebuilding the domain by hand.
    typed_data: dict


# Which wallet each nullifier was first attested for. A person retrying with the
# same wallet is normal and allowed; the same person arriving with a second
# wallet is the attack.
#
# In memory, which is honest about what it is: it does not survive a restart and
# it does not hold across replicas. The durable version of this check belongs on
# chain — the contract binding a nullifier to the first visitor it pays, and
# refusing a second — because that is the only copy an attacker cannot outlive.
_bound: dict[str, str] = {}


def clear_bindings() -> None:
    _bound.clear()


def _bind(nullifier_hash: str, visitor: str) -> None:
    key = nullifier_hash.lower()
    already = _bound.get(key)
    if already is not None and already != visitor.lower():
        raise NullifierAlreadyBound(
            "that World ID is already verified for a different wallet"
        )
    _bound[key] = visitor.lower()


def verify_with_world(idkit_response: dict) -> str:
    """Ask World whether this proof is real, and return the nullifier.

    The proof is forwarded exactly as IDKit produced it. Rebuilding it here
    would mean this service deciding what the user proved, which is the thing
    the design is trying to avoid — we relay the question and repeat the answer.
    """
    config = get_config()
    if not config.world_rp_id:
        raise WorldError("WORLD_RP_ID is not set")

    url = f"{config.world_api_url.rstrip('/')}/{config.world_rp_id}"
    try:
        response = httpx.post(
            url,
            json=idkit_response,
            timeout=config.world_timeout_seconds,
        )
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WorldError(f"could not reach World: {exc}") from exc

    # A 400 carries the reason the proof failed, and that reason is the useful
    # part — "already verified", "expired", "wrong action". Passing it through
    # is what lets the app tell a person what to do next.
    if response.status_code >= 400 or not body.get("success"):
        detail = body.get("detail") or body.get("code") or response.text[:200]
        raise WorldError(f"World rejected the proof: {detail}")

    nullifier = body.get("nullifier")
    if not nullifier:
        # Success without a nullifier is nonsense: the nullifier is the whole
        # answer. Better to fail here than to sign an attestation over nothing.
        raise WorldError("World returned success with no nullifier")
    return nullifier


def build_typed_data(*, visitor: str, nullifier_hash: str, expiry: int) -> dict:
    config = get_config()
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            STRUCT_NAME: ATTESTATION_TYPE,
        },
        "primaryType": STRUCT_NAME,
        "domain": {
            "name": "ZoneGo",
            "version": "1",
            "chainId": config.chain_id,
            "verifyingContract": config.visit_registry_address,
        },
        "message": {
            "visitor": visitor,
            "nullifierHash": nullifier_hash,
            "expiry": expiry,
        },
    }


def attest(*, visitor: str, nullifier_hash: str) -> Attestation:
    """Sign that World confirmed this wallet belongs to a verified human.

    Short-lived on purpose. The attestation travels from this response into a
    claim in the same session, so two minutes is generous — and one read off a
    screen is already worthless by the time anyone could use it.
    """
    config = get_config()
    if not config.attester_private_key:
        raise WorldError("ATTESTER_PRIVATE_KEY is not set")

    _bind(nullifier_hash, visitor)

    expiry = int(time.time()) + config.attestation_ttl_seconds
    typed_data = build_typed_data(
        visitor=visitor, nullifier_hash=nullifier_hash, expiry=expiry
    )

    signed = Account.from_key(config.attester_private_key).sign_message(
        encode_typed_data(full_message=typed_data)
    )

    return Attestation(
        visitor=visitor,
        nullifier_hash=nullifier_hash,
        expiry=expiry,
        signature="0x" + signed.signature.hex().removeprefix("0x"),
        typed_data=typed_data,
    )


def attester_address() -> str:
    """The address the contract checks `ECDSA.recover` against."""
    config = get_config()
    if not config.attester_private_key:
        raise WorldError("ATTESTER_PRIVATE_KEY is not set")
    return Account.from_key(config.attester_private_key).address
