"""The Merkle tree that makes a fraud score auditable after the fact.

A score only we hold is a score we can rewrite later to justify a charge.
Committing one root per epoch fixes every score in that window at once: we can
still be wrong, but we cannot be wrong quietly, and a visitor whose reward was
held can prove what we said about them and when.

The leaf format is a contract with `FraudOracle.verifyScore`, the same way
`schema/events.md` is a contract with the subgraph. Both sides have to agree on
this or every proof fails on chain:

    leaf  = keccak256(keccak256(abi.encode(address wallet, uint16 score)))
    node  = keccak256(a + b), with the pair sorted so a < b

Two choices worth stating, because neither is arbitrary:

Double hashing is OpenZeppelin's guard against a second preimage. An internal
node is one keccak over 64 bytes, so a single-hashed 64-byte leaf could be
passed off as an internal node and a proof forged from it.

Sorting each pair is what `MerkleProof.verify` does, and it is why a proof
carries no left/right bits — just siblings.

Scores travel as basis points, 0 to 10_000, because `verifyScore` takes a
uint16 and a float does not hash to the same bytes twice across languages.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from eth_abi import encode
from web3 import Web3

# 0.7213 becomes 7213. Four decimals is finer than the model's own resolution
# and leaves the uint16 with room to spare.
SCORE_SCALE = 10_000


def score_to_bps(score: float) -> int:
    """A model score in 0..1 as the integer the contract verifies."""
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"score outside 0..1: {score}")
    return round(score * SCORE_SCALE)


def leaf(wallet: str, score_bps: int) -> bytes:
    if not 0 <= score_bps <= SCORE_SCALE:
        raise ValueError(f"score outside 0..{SCORE_SCALE}: {score_bps}")
    packed = encode(["address", "uint16"], [Web3.to_checksum_address(wallet), score_bps])
    return Web3.keccak(Web3.keccak(packed))


def _node(a: bytes, b: bytes) -> bytes:
    return Web3.keccak(a + b if a < b else b + a)


@dataclass(frozen=True)
class Tree:
    """One epoch's scores, with the root to commit and the proofs to hand out."""

    layers: tuple[tuple[bytes, ...], ...]
    index: Mapping[bytes, int]

    @property
    def root(self) -> str:
        return "0x" + self.layers[-1][0].hex()

    @property
    def size(self) -> int:
        return len(self.layers[0])

    def proof(self, wallet: str, score_bps: int) -> list[str]:
        """The siblings that rebuild the root, for this wallet and this score.

        The score is part of the question: a proof is only ever valid for the
        exact pair that was committed, which is what stops us from claiming
        afterwards that we had scored someone differently.
        """
        target = leaf(wallet, score_bps)
        position = self.index.get(target)
        if position is None:
            raise KeyError(f"{wallet} was not scored in this epoch")

        out: list[str] = []
        for level in self.layers[:-1]:
            sibling = position ^ 1
            # An odd node at the end of a level has no sibling; it is promoted
            # unchanged, so it contributes nothing to the proof.
            if sibling < len(level):
                out.append("0x" + level[sibling].hex())
            position //= 2
        return out


def build(scores: Mapping[str, int]) -> Tree:
    """A tree over wallet/score pairs, in basis points.

    A mapping rather than a list because one wallet scored twice in the same
    epoch is a bug, not a case to resolve. Leaves are sorted so that the same
    scores always produce the same root — an epoch anyone can rebuild and check
    against the chain is the entire point.
    """
    if not scores:
        raise ValueError("an epoch with no scores has nothing to commit")

    leaves = sorted(leaf(wallet, bps) for wallet, bps in scores.items())
    index = {node: i for i, node in enumerate(leaves)}

    layers: list[tuple[bytes, ...]] = [tuple(leaves)]
    while len(layers[-1]) > 1:
        level = layers[-1]
        layers.append(
            tuple(
                _node(level[i], level[i + 1]) if i + 1 < len(level) else level[i]
                for i in range(0, len(level), 2)
            )
        )

    return Tree(layers=tuple(layers), index=index)


def verify(root: str, wallet: str, score_bps: int, proof: list[str]) -> bool:
    """The same walk `MerkleProof.verify` does on chain, for tests and the panel."""
    node = leaf(wallet, score_bps)
    for step in proof:
        node = _node(node, bytes.fromhex(step.removeprefix("0x")))
    return node.hex() == root.removeprefix("0x")
