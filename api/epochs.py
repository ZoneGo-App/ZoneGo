"""Committing an hour of fraud scores at once, so none of them can move later.

A score decides whether a reward is paid or held. Held is the interesting case:
it is us saying no, and a person who is told no deserves to be able to check
that we did not change our mind afterwards to justify it. Publishing one Merkle
root per hour fixes every score in that hour together — after that we can still
be wrong, but not quietly.

An epoch is not stored anywhere. It is a pure function of the chain:

    the visits the subgraph holds in [start, end)  ->  scores  ->  root

so anybody can rebuild the same root from public data and compare it to what we
published. Keeping a database of our own would put us back in the position the
root exists to remove. What is cached here is only the arithmetic.

The current epoch is never committed. It is still collecting visits, so its
root would change every time somebody walks into a store — the window has to
close before the number means anything.
"""

import time
from dataclasses import dataclass

from api import merkle, subgraph
from api.config import get_config
from api.mock_data import MOCK_EXPLORERS
from api.routers.score import wallet_score


class EpochNotClosed(RuntimeError):
    pass


@dataclass(frozen=True)
class Commitment:
    """One closed epoch: the root to publish, and the scores behind it."""

    epoch: int
    start: int
    end: int
    root: str
    # Wallet to score in basis points, exactly what the leaves were built from.
    scores: dict[str, int]
    tree: merkle.Tree

    @property
    def wallets(self) -> int:
        return len(self.scores)


def epoch_at(timestamp: int) -> int:
    return timestamp // get_config().epoch_seconds


def current_epoch() -> int:
    return epoch_at(int(time.time()))


def window(epoch: int) -> tuple[int, int]:
    """[start, end) of an epoch, in unix seconds."""
    size = get_config().epoch_seconds
    return epoch * size, (epoch + 1) * size


_cache: dict[int, Commitment] = {}


def clear_cache() -> None:
    _cache.clear()


def wallets_in(start: int, end: int) -> list[str]:
    """Everyone with a visit in [start, end), lowercased and sorted.

    In mock mode the sample explorers stand in for the index, so the panel has
    a real root and a real proof to build against before the chain has anybody
    on it. Only the list of wallets is invented — the tree over them is the one
    that will be committed.
    """
    if get_config().mock_mode:
        return sorted(row.address.lower() for row in MOCK_EXPLORERS)
    return subgraph.visitors_between(start, end)


def build(epoch: int) -> Commitment | None:
    """The commitment for a closed epoch, or None if nobody visited in it.

    Rebuilding an epoch has to give the same root every time or the whole
    argument collapses, so nothing here reads a clock except the check that the
    window is over.
    """
    if epoch >= current_epoch():
        raise EpochNotClosed(f"epoch {epoch} is still open")

    cached = _cache.get(epoch)
    if cached is not None:
        return cached

    start, end = window(epoch)
    wallets = wallets_in(start, end)
    if not wallets:
        # A quiet hour. Committing a root over nothing would be a transaction
        # that says nothing, so there is no commitment to make.
        return None

    scores = {wallet: merkle.score_to_bps(wallet_score(wallet)) for wallet in wallets}
    tree = merkle.build(scores)

    commitment = Commitment(
        epoch=epoch, start=start, end=end, root=tree.root, scores=scores, tree=tree
    )
    _cache[epoch] = commitment
    return commitment


def proof_for(epoch: int, wallet: str) -> tuple[int, list[str]] | None:
    """The score we committed for a wallet, and the proof of it.

    None when that wallet had no visit in the epoch — which is a different
    answer from a score of zero, and the panel has to be able to tell them
    apart.
    """
    commitment = build(epoch)
    if commitment is None:
        return None

    score_bps = commitment.scores.get(wallet.lower())
    if score_bps is None:
        return None
    return score_bps, commitment.tree.proof(wallet, score_bps)
