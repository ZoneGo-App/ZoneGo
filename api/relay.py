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

One thing it does decide, and this is not settled: `visitor` sits outside the
signed struct, so whoever sends the transaction names who gets paid. Until
World's proof binds the nullifier to an address, that choice is ours.
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
            {"name": "nullifierHash", "type": "bytes32"},
        ],
    }
]


class RelayError(RuntimeError):
    pass


@dataclass(frozen=True)
class Claim:
    """The four signed fields, plus who is claiming and which human they are."""

    campaign_id: int
    # The merchant's single-use nonce from the QR. Not the account nonce below.
    nonce: int
    expiry: int
    geohash: str
    signature: str
    visitor: str
    nullifier_hash: str


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
    call = registry.functions.claim(
        (
            claim.campaign_id,
            claim.nonce,
            claim.expiry,
            _bytes(claim.geohash),
            Web3.to_checksum_address(claim.visitor),
        ),
        _bytes(claim.signature),
        _bytes(claim.nullifier_hash),
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
