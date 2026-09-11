"""Sending a transaction from a key that more than one code path shares.

The relay and the hourly epoch job sign with the same key, and a busy minute
has two visitors claiming at once. Every send asks the node for the next nonce,
and the `latest` count ignores transactions still waiting in the mempool — so
two sends a second apart got the same number, the node kept one, and the other
visitor was refused a claim that was perfectly valid.

Two changes close it. The count is read from `pending`, so a transaction the
node has already accepted is counted. And read, sign and send happen under one
lock per address, so no two threads in this process read the count between
each other's sends.
"""

import threading

from web3 import Web3

_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _lock_for(address: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(address.lower(), threading.Lock())


def send(w3: Web3, account, call, *, chain_id: int) -> str:
    """Build, sign and send one contract call. Returns the 0x-prefixed hash.

    Web3 errors pass straight through, so each caller wraps them in its own
    error type and keeps its own rule about what is safe to repeat.
    """
    with _lock_for(account.address):
        transaction = call.build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address, "pending"),
                "chainId": chain_id,
            }
        )
        signed = account.sign_transaction(transaction)
        sent = w3.eth.send_raw_transaction(signed.raw_transaction)
    return "0x" + sent.hex().removeprefix("0x")
