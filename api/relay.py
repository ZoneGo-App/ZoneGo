"""Sending a claim on the visitor's behalf, and paying the gas for it.

This is the one place the API holds a key, and it is worth being precise about
what that key can and cannot do. It signs a transaction — it does not sign the
visit. The merchant's EIP-712 signature travels through here untouched, and the
contract recovers the merchant from it; a relay that altered any field would
produce a signature that recovers to somebody else and the claim reverts.

So the key buys the visitor gas, nothing more. If this service disappeared, the
visitor could send the identical call from their own wallet and be paid the
same amount, which is why `relayed` is a field in the response and not a
requirement of the protocol.

The visitor used to sit outside the signed struct, which meant whoever sent the
transaction named who got paid — a real hole, and the contract closed it. Now
two signatures travel through here and neither is ours to alter: the merchant's
over the visit, and the attester's over what World answered.
"""

from dataclasses import dataclass

from eth_account import Account
from web3 import Web3
from web3.exceptions import Web3Exception

from api.chain import ZERO_ADDRESS
from api.config import get_config

# Only `claim`. The tuple mirrors VisitSig in VisitRegistry.sol; the field order
# is part of the ABI encoding, so reordering it here produces a transaction the
# contract decodes into different values rather than one it rejects.
VISIT_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "claim",
        "stateMutability": "nonpayable",
        "outputs": [],
        "inputs": [
            {
                "name": "sig",
                "type": "tuple",
                "components": [
                    {"name": "campaignId", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "expiry", "type": "uint64"},
                    {"name": "geohash", "type": "bytes32"},
                    {"name": "visitor", "type": "address"},
                ],
            },
            {"name": "signature", "type": "bytes"},
            # World's answer, signed by the attester. The contract reads the
            # nullifier out of this struct rather than from a loose argument,
            # so there is exactly one place it can come from.
            {
                "name": "attestation",
                "type": "tuple",
                "components": [
                    {"name": "visitor", "type": "address"},
                    {"name": "nullifierHash", "type": "bytes32"},
                    {"name": "expiry", "type": "uint64"},
                ],
            },
            {"name": "attestationSignature", "type": "bytes"},
        ],
    }
]


class RelayError(RuntimeError):
    pass


@dataclass(frozen=True)
class Claim:
    """The merchant's signed visit, and the attestation naming the human.

    Two independent expiries, because they answer to different clocks: the
    merchant's signature dies with the QR, the attestation dies with the World
    session that produced it.
    """

    campaign_id: int
    # The merchant's single-use nonce from the QR. Not the account nonce below.
    nonce: int
    expiry: int
    geohash: str
    signature: str
    visitor: str
    # All three from POST /world/verify, and they travel together or not at
    # all: the signature only recovers over this exact nullifier and expiry.
    nullifier_hash: str
    attestation_expiry: int
    attestation_signature: str


def _bytes(value: str) -> bytes:
    return bytes.fromhex(value.removeprefix("0x"))


def send_claim(claim: Claim) -> str:
    """Submit the claim and return the transaction hash.

    Gas is estimated before signing, so a claim the contract would reject costs
    an `eth_estimateGas` instead of a reverted transaction. That is the same
    filter the route applies earlier and cheaper — this one catches what only
    the contract knows, like a nonce already spent.
    """
    config = get_config()
    if not config.rpc_url:
        raise RelayError("RPC_URL is not set")
    if config.visit_registry_address == ZERO_ADDRESS:
        raise RelayError("VISIT_REGISTRY_ADDRESS is not set")
    if not config.relay_private_key:
        raise RelayError("RELAY_PRIVATE_KEY is not set")

    w3 = Web3(
        Web3.HTTPProvider(
            config.rpc_url,
            request_kwargs={"timeout": config.rpc_timeout_seconds},
        )
    )
    account = Account.from_key(config.relay_private_key)
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(config.visit_registry_address),
        abi=VISIT_REGISTRY_ABI,
    )

    # The visitor travels inside the signed struct now, not beside it. The
    # relay cannot swap it for an address of its own without the merchant's
    # signature failing to recover — which is the point.
    visitor = Web3.to_checksum_address(claim.visitor)

    call = registry.functions.claim(
        (
            claim.campaign_id,
            claim.nonce,
            claim.expiry,
            _bytes(claim.geohash),
            visitor,
        ),
        _bytes(claim.signature),
        # The same `visitor` fills both structs on purpose. The contract
        # requires them equal, so passing one value twice removes the only way
        # this call could contradict itself.
        (visitor, _bytes(claim.nullifier_hash), claim.attestation_expiry),
        _bytes(claim.attestation_signature),
    )

    try:
        transaction = call.build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": config.chain_id,
            }
        )
        signed = account.sign_transaction(transaction)
        sent = w3.eth.send_raw_transaction(signed.raw_transaction)
    except Web3Exception as exc:
        # Never let the underlying error carry the key or the signed payload
        # into a response body; only what the node said is safe to repeat.
        raise RelayError(f"relay failed: {exc}") from exc

    return "0x" + sent.hex().removeprefix("0x")
