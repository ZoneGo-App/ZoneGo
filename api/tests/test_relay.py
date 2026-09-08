"""The relay, against a node that answers but never sees a real transaction.

Signing happens locally, so the only thing crossing the wire is the finished
payload. What these check is that the four signed fields survive the trip
unchanged — a relay that reshaped any of them would produce a signature the
contract recovers to somebody other than the merchant.
"""

import pytest
from eth_abi import decode
from web3 import Web3

from api import relay
from api.config import get_config

REGISTRY = "0xD33f2e26f11Fe011835D791EbA1BFE123479998A"
# Test key, never funded, never used anywhere but here.
RELAY_KEY = "0x" + "11" * 32
TX_HASH = "0x" + "ab" * 32

A_CLAIM = relay.Claim(
    campaign_id=1,
    nonce=12345,
    expiry=1788800000,
    geohash="0x" + b"dr5rsked".hex().ljust(64, "0"),
    signature="0x" + "b2" * 65,
    visitor="0x" + "a1" * 20,
    nullifier_hash="0x" + "c3" * 32,
)

BLOCK = {
    "number": hex(1),
    "baseFeePerGas": hex(1_000_000),
    "gasLimit": hex(30_000_000),
    "gasUsed": hex(1),
    "timestamp": hex(1),
    "hash": "0x" + "11" * 32,
    "parentHash": "0x" + "22" * 32,
    "miner": "0x" + "33" * 20,
    "difficulty": hex(0),
    "totalDifficulty": hex(0),
    "size": hex(1),
    "extraData": "0x",
    "transactions": [],
    "uncles": [],
    "logsBloom": "0x" + "00" * 256,
    "sha3Uncles": "0x" + "44" * 32,
    "stateRoot": "0x" + "55" * 32,
    "receiptsRoot": "0x" + "66" * 32,
    "transactionsRoot": "0x" + "77" * 32,
    "nonce": "0x" + "00" * 8,
    "mixHash": "0x" + "88" * 32,
}


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "rpc_url", "https://example.test/rpc")
    monkeypatch.setattr(config, "visit_registry_address", REGISTRY)
    monkeypatch.setattr(config, "relay_private_key", RELAY_KEY)


def node(monkeypatch, *, estimate_gas=hex(210_000)):
    """A node that accepts everything. `sent` keeps the raw payload."""
    sent: dict[str, str] = {}

    def fake(self, method, params):
        answers = {
            "eth_chainId": hex(84532),
            "eth_getTransactionCount": hex(3),
            "eth_maxPriorityFeePerGas": hex(1_000_000),
            "eth_getBlockByNumber": BLOCK,
            "eth_estimateGas": estimate_gas,
        }
        if method == "eth_sendRawTransaction":
            sent["raw"] = params[0]
            return {"jsonrpc": "2.0", "id": 1, "result": TX_HASH}
        if isinstance(answers.get(method), Exception):
            raise answers[method]
        return {"jsonrpc": "2.0", "id": 1, "result": answers[method]}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    return sent


def test_a_claim_comes_back_with_the_transaction_hash(monkeypatch):
    node(monkeypatch)
    assert relay.send_claim(A_CLAIM) == TX_HASH


def test_the_signed_fields_reach_the_contract_unchanged(monkeypatch):
    """The point of the relay: it pays, it does not edit."""
    sent = node(monkeypatch)
    relay.send_claim(A_CLAIM)

    # Strip the 4-byte selector, then read the arguments back out.
    raw = bytes.fromhex(sent["raw"].removeprefix("0x"))
    # The signed transaction is RLP; the calldata is what we can find inside it
    # by looking for the selector we know we produced.
    selector = Web3.keccak(
        text="claim((uint256,uint256,uint64,bytes32,address),bytes,bytes32)"
    )[:4]
    start = raw.index(selector) + 4
    sig, signature, nullifier = decode(
        ["(uint256,uint256,uint64,bytes32,address)", "bytes", "bytes32"],
        raw[start:],
    )

    assert sig[0] == A_CLAIM.campaign_id
    assert sig[1] == A_CLAIM.nonce
    assert sig[2] == A_CLAIM.expiry
    assert "0x" + sig[3].hex() == A_CLAIM.geohash
    # Inside the struct now, so the relay cannot redirect the payment without
    # the merchant's signature failing to recover.
    assert sig[4].lower() == A_CLAIM.visitor
    assert "0x" + signature.hex() == A_CLAIM.signature
    assert "0x" + nullifier.hex() == A_CLAIM.nullifier_hash


def test_a_claim_the_contract_would_reject_never_costs_gas(monkeypatch):
    """Estimation fails first, so a spent nonce is an error and not a revert."""

    def fake(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": hex(84532)}
        if method == "eth_estimateGas":
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": 3, "message": "execution reverted: NonceAlreadyUsed"},
            }
        return {"jsonrpc": "2.0", "id": 1, "result": hex(3)}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    with pytest.raises(relay.RelayError):
        relay.send_claim(A_CLAIM)


@pytest.mark.parametrize(
    "missing", ["rpc_url", "visit_registry_address", "relay_private_key"]
)
def test_a_missing_setting_fails_before_anything_is_signed(monkeypatch, missing):
    blank = "0x0000000000000000000000000000000000000000" if "address" in missing else ""
    monkeypatch.setattr(get_config(), missing, blank)
    with pytest.raises(relay.RelayError):
        relay.send_claim(A_CLAIM)


def test_the_key_never_reaches_the_error_message(monkeypatch):
    """A 502 body carries this straight to the caller."""

    def fake(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": hex(84532)}
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "boom"}}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    with pytest.raises(relay.RelayError) as caught:
        relay.send_claim(A_CLAIM)
    assert RELAY_KEY not in str(caught.value)
    assert RELAY_KEY[2:] not in str(caught.value)
