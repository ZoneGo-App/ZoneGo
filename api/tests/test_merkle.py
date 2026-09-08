"""The Merkle tree, checked the way the contract will check it.

Every test that matters here is really one question: can a visitor prove what
we said about them, and can we not say something else afterwards. The odd-size
cases get their own loop because a level with a leftover node is where Merkle
implementations quietly go wrong — the root still looks fine, and only some
proofs fail.
"""

import pytest

from api import merkle


def wallets(n: int) -> dict[str, int]:
    """n distinct wallets with distinct scores."""
    return {"0x" + f"{i + 1:040x}": (i * 137) % merkle.SCORE_SCALE for i in range(n)}


def test_a_proof_rebuilds_the_root():
    scores = wallets(6)
    tree = merkle.build(scores)
    wallet, bps = next(iter(scores.items()))
    assert merkle.verify(tree.root, wallet, bps, tree.proof(wallet, bps))


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 9, 16, 17, 33])
def test_every_wallet_can_prove_itself_at_any_size(n):
    """Sizes that are not powers of two are where the leftover node lives."""
    scores = wallets(n)
    tree = merkle.build(scores)
    assert tree.size == n
    for wallet, bps in scores.items():
        assert merkle.verify(tree.root, wallet, bps, tree.proof(wallet, bps))


def test_a_score_we_did_not_commit_does_not_verify():
    """The property the whole thing exists for: we cannot rewrite a score."""
    scores = wallets(8)
    tree = merkle.build(scores)
    wallet, bps = next(iter(scores.items()))
    proof = tree.proof(wallet, bps)
    assert not merkle.verify(tree.root, wallet, bps + 1, proof)


def test_another_wallets_proof_does_not_work():
    scores = wallets(8)
    tree = merkle.build(scores)
    (first, first_bps), (second, second_bps) = list(scores.items())[:2]
    assert not merkle.verify(tree.root, first, first_bps, tree.proof(second, second_bps))


def test_a_wallet_nobody_scored_has_no_proof():
    tree = merkle.build(wallets(4))
    with pytest.raises(KeyError):
        tree.proof("0x" + "ff" * 20, 100)


def test_the_root_does_not_depend_on_insertion_order():
    """An epoch anyone can rebuild has to hash the same both times."""
    scores = wallets(9)
    reversed_scores = dict(reversed(list(scores.items())))
    assert merkle.build(scores).root == merkle.build(reversed_scores).root


def test_one_wallet_is_its_own_root():
    scores = wallets(1)
    wallet, bps = next(iter(scores.items()))
    tree = merkle.build(scores)
    assert tree.proof(wallet, bps) == []
    assert tree.root == "0x" + merkle.leaf(wallet, bps).hex()


def test_an_empty_epoch_has_nothing_to_commit():
    with pytest.raises(ValueError):
        merkle.build({})


def test_the_leaf_is_double_hashed():
    """Guards the choice, not the value: single hashing is forgeable."""
    from web3 import Web3

    from eth_abi import encode

    wallet = "0x" + "11" * 20
    packed = encode(["address", "uint16"], [Web3.to_checksum_address(wallet), 7213])
    assert merkle.leaf(wallet, 7213) == Web3.keccak(Web3.keccak(packed))


def test_pairs_are_sorted_so_a_proof_needs_no_direction():
    a, b = merkle.leaf("0x" + "11" * 20, 1), merkle.leaf("0x" + "22" * 20, 2)
    assert merkle._node(a, b) == merkle._node(b, a)


def test_a_score_becomes_basis_points():
    assert merkle.score_to_bps(0.7213) == 7213
    assert merkle.score_to_bps(0.0) == 0
    assert merkle.score_to_bps(1.0) == merkle.SCORE_SCALE


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_a_score_outside_the_range_is_refused(bad):
    with pytest.raises(ValueError):
        merkle.score_to_bps(bad)
