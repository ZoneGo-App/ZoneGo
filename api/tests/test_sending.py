"""One key, one nonce at a time.

The relay and the epoch job share a key. These pin the two things that stop a
second transaction from reusing the first one's nonce: the count includes the
mempool, and nobody reads it while another send is still in flight.
"""

import threading
import time

from eth_account import Account

from api import sending

# A key that exists only here.
ACCOUNT = Account.from_key("0x" + "33" * 32)


class Node:
    """Answers the two calls a send makes, and watches for overlap."""

    def __init__(self):
        self.block_identifiers: list[str] = []
        self.sent = 0
        self.in_flight = 0
        self.most_in_flight = 0
        self._lock = threading.Lock()

    def get_transaction_count(self, address, block_identifier="latest"):
        with self._lock:
            self.block_identifiers.append(block_identifier)
            self.in_flight += 1
            self.most_in_flight = max(self.most_in_flight, self.in_flight)
            count = self.sent
        # The window a race needs: long enough for a second thread to read the
        # same count if nothing stops it.
        time.sleep(0.02)
        return count

    def send_raw_transaction(self, raw):
        with self._lock:
            self.sent += 1
            self.in_flight -= 1
        return bytes(32)


class W3:
    def __init__(self):
        self.eth = Node()


class Call:
    def __init__(self):
        self.nonces: list[int] = []
        self._lock = threading.Lock()

    def build_transaction(self, params):
        with self._lock:
            self.nonces.append(params["nonce"])
        return {
            "to": "0x" + "11" * 20,
            "value": 0,
            "gas": 21_000,
            "maxFeePerGas": 1,
            "maxPriorityFeePerGas": 1,
            "nonce": params["nonce"],
            "chainId": params["chainId"],
            "data": b"",
        }


def test_the_nonce_counts_what_is_still_in_the_mempool():
    """`latest` ignores a claim the node accepted a second ago."""
    w3 = W3()
    sending.send(w3, ACCOUNT, Call(), chain_id=84532)
    assert w3.eth.block_identifiers == ["pending"]


def test_simultaneous_sends_never_share_a_nonce():
    """Two visitors claiming in the same second both get paid."""
    w3, call = W3(), Call()
    threads = [
        threading.Thread(target=sending.send, args=(w3, ACCOUNT, call), kwargs={"chain_id": 84532})
        for _ in range(5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert w3.eth.most_in_flight == 1
    assert sorted(call.nonces) == [0, 1, 2, 3, 4]


def test_it_returns_a_prefixed_transaction_hash():
    assert sending.send(W3(), ACCOUNT, Call(), chain_id=84532) == "0x" + "00" * 32
