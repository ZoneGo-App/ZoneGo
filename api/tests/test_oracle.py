"""Publishing a root, against a node that answers but never mines anything.

The property worth testing is not that a transaction goes out — it is that the
job asks the chain what it already knows before spending gas to find out, and
that a key never reaches a log line.
"""

import pytest
from eth_abi import decode
from web3 import Web3

from api import oracle
from api.config import get_config

ORACLE = "0x4a2C8E9d1B3F5a7C9e0D2b4F6a8C0e2D4b6F8a0C"
# Test key, never funded, never used anywhere but here.
OPERATOR_KEY = "0x" + "22" * 32
TX_HASH = "0x" + "cd" * 32
A_ROOT = "0x" + "7e" * 32

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
    monkeypatch.setattr(config, "fraud_oracle_address", ORACLE)
    monkeypatch.setattr(config, "fraud_operator_private_key", OPERATOR_KEY)


def word(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def node(monkeypatch, *, root=None, epoch=0):
    """A node that accepts everything. `sent` keeps the raw payload.

    `eth_call` answers whichever view was asked for by looking at the selector,
    so a test can put the contract in a state and let the code discover it.
    """
    sent: dict[str, str] = {}
    current_root = word(0) if root is None else root
    current_epoch = word(epoch)

    def fake(self, method, params):
        if method == "eth_call":
            data = params[0]["data"]
            if data.startswith(Web3.keccak(text="currentRoot()")[:4].hex()):
                return {"jsonrpc": "2.0", "id": 1, "result": current_root}
            return {"jsonrpc": "2.0", "id": 1, "result": current_epoch}
        if method == "eth_sendRawTransaction":
            sent["raw"] = params[0]
            return {"jsonrpc": "2.0", "id": 1, "result": TX_HASH}
        answers = {
            "eth_chainId": hex(84532),
            "eth_getTransactionCount": hex(7),
            "eth_maxPriorityFeePerGas": hex(1_000_000),
            "eth_getBlockByNumber": BLOCK,
            "eth_estimateGas": hex(120_000),
        }
        return {"jsonrpc": "2.0", "id": 1, "result": answers[method]}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    return sent


def test_it_is_not_configured_until_both_halves_arrive(monkeypatch):
    """One without the other is a job that fails every hour, loudly."""
    assert oracle.configured() is True
    monkeypatch.setattr(get_config(), "fraud_operator_private_key", "")
    assert oracle.configured() is False


def test_an_empty_oracle_has_no_published_epoch(monkeypatch):
    """The contract accepts any number for the first root, so there is no floor."""
    node(monkeypatch)
    assert oracle.published_epoch() is None


def test_a_committed_root_reports_its_epoch(monkeypatch):
    node(monkeypatch, root=A_ROOT, epoch=41)
    assert oracle.published_epoch() == 41


def test_the_root_and_epoch_reach_the_contract_unchanged(monkeypatch):
    sent = node(monkeypatch)
    assert oracle.commit_epoch(root=A_ROOT, epoch=42) == TX_HASH

    raw = bytes.fromhex(sent["raw"].removeprefix("0x"))
    selector = Web3.keccak(text="commitEpoch(bytes32,uint64)")[:4]
    start = raw.index(selector) + 4
    root, epoch = decode(["bytes32", "uint64"], raw[start:])

    assert "0x" + root.hex() == A_ROOT
    assert epoch == 42


def test_a_root_the_contract_would_refuse_never_costs_gas(monkeypatch):
    """Estimation fails first, so a repeated epoch is an error not a revert."""

    def fake(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": hex(84532)}
        if method == "eth_estimateGas":
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": 3,
                    "message": "execution reverted: EpochNotIncreasing",
                },
            }
        return {"jsonrpc": "2.0", "id": 1, "result": hex(7)}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    with pytest.raises(oracle.OracleError):
        oracle.commit_epoch(root=A_ROOT, epoch=1)


def test_the_key_never_reaches_the_error_message(monkeypatch):
    """These errors go to a log that a teammate reads over a shoulder."""

    def fake(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": hex(84532)}
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "boom"}}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    with pytest.raises(oracle.OracleError) as caught:
        oracle.commit_epoch(root=A_ROOT, epoch=42)
    assert OPERATOR_KEY not in str(caught.value)
    assert OPERATOR_KEY[2:] not in str(caught.value)


@pytest.mark.parametrize("missing", ["rpc_url", "fraud_operator_private_key"])
def test_a_missing_setting_fails_before_anything_is_signed(monkeypatch, missing):
    monkeypatch.setattr(get_config(), missing, "")
    with pytest.raises(oracle.OracleError):
        oracle.commit_epoch(root=A_ROOT, epoch=42)


def test_the_operator_address_is_derived_from_the_key():
    """What Sebastián puts in the constructor has to match what signs."""
    assert oracle.operator_address().startswith("0x")
    assert len(oracle.operator_address()) == 42
