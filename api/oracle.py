"""Publishing an epoch's root, and the one key allowed to do it.

An epoch is a claim about a batch of scores, and a claim nobody can check is
worth nothing. Putting the root on chain is what turns "the model scored you
0.7213" into something a visitor can verify against a number that was published
before they appealed — and before we knew they would.

The key that signs it has a setting of its own, and that setting currently holds
the relay's key. A separate key would buy less than it sounds: both are read from
the same environment by the same process, so whoever gets one gets both. What
sharing actually costs is the nonce — the relay and this job ask the node for the
same next number, and two sends in the same second lose one of them. One
publication an hour keeps that window narrow, and widening it is a value to
change rather than code to write.

`commitEpoch` refuses an epoch that is not greater than the one on chain, which
is what makes a restart safe — and what makes reading the chain first cheaper
than discovering it in a reverted transaction.
"""

from eth_account import Account
from web3 import Web3
from web3.exceptions import Web3Exception

from api.chain import ZERO_ADDRESS
from api.config import get_config

ZERO_ROOT = "0x" + "00" * 32

FRAUD_ORACLE_ABI = [
    {
        "type": "function",
        "name": "commitEpoch",
        "stateMutability": "nonpayable",
        "outputs": [],
        "inputs": [
            {"name": "root", "type": "bytes32"},
            {"name": "epoch", "type": "uint64"},
        ],
    },
    {
        "type": "function",
        "name": "currentEpoch",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint64"}],
    },
    {
        "type": "function",
        "name": "currentRoot",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
]


class OracleError(RuntimeError):
    pass


def configured() -> bool:
    """Whether there is a contract to publish to and a key to sign with.

    Both arrive from Sebastián's redeploy, so until then the job runs the whole
    path and stops here rather than failing every hour.
    """
    config = get_config()
    return bool(
        config.rpc_url
        and config.fraud_oracle_address != ZERO_ADDRESS
        and config.fraud_operator_private_key
    )


def _connect():
    config = get_config()
    if not config.rpc_url:
        raise OracleError("RPC_URL is not set")
    if config.fraud_oracle_address == ZERO_ADDRESS:
        raise OracleError("FRAUD_ORACLE_ADDRESS is not set")

    w3 = Web3(
        Web3.HTTPProvider(
            config.rpc_url,
            request_kwargs={"timeout": config.rpc_timeout_seconds},
        )
    )
    oracle = w3.eth.contract(
        address=Web3.to_checksum_address(config.fraud_oracle_address),
        abi=FRAUD_ORACLE_ABI,
    )
    return w3, oracle


def published_epoch() -> int | None:
    """The last epoch with a root on chain, or None when there is none yet.

    Asked before publishing because the job's memory of what it has done dies
    with the process. After a redeploy the chain is the only thing that still
    remembers, and one view call is cheaper than a transaction that reverts.
    """
    _, oracle = _connect()
    try:
        root = oracle.functions.currentRoot().call()
        if "0x" + root.hex().removeprefix("0x") == ZERO_ROOT:
            # Nothing committed yet. The contract accepts any epoch number for
            # the first root, so there is no floor to compare against.
            return None
        return int(oracle.functions.currentEpoch().call())
    except Web3Exception as exc:
        raise OracleError(f"could not read the oracle: {exc}") from exc


def commit_epoch(*, root: str, epoch: int) -> str:
    """Publish one epoch's root and return the transaction hash.

    Gas is estimated before signing, so an epoch the contract would refuse —
    already published, or signed by the wrong key — costs an `eth_estimateGas`
    instead of a reverted transaction with a fee attached.
    """
    config = get_config()
    if not config.fraud_operator_private_key:
        raise OracleError("FRAUD_OPERATOR_PRIVATE_KEY is not set")

    w3, oracle = _connect()
    account = Account.from_key(config.fraud_operator_private_key)

    call = oracle.functions.commitEpoch(
        bytes.fromhex(root.removeprefix("0x")),
        epoch,
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
        # This runs unattended and its errors reach a log, so never let the
        # underlying message carry the key or the signed payload with it.
        raise OracleError(f"commitEpoch failed: {exc}") from exc

    return "0x" + sent.hex().removeprefix("0x")


def operator_address() -> str:
    """The address `commitEpoch` checks `msg.sender` against."""
    config = get_config()
    if not config.fraud_operator_private_key:
        raise OracleError("FRAUD_OPERATOR_PRIVATE_KEY is not set")
    return Account.from_key(config.fraud_operator_private_key).address
