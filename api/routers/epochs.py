"""Reading an epoch back: the root we published, and one wallet's proof of it.

Nothing here computes anything. `api/epochs.py` rebuilds an epoch from the
subgraph on demand, and this only decides what each failure means to a caller,
because three of them look alike from outside and are not:

    still open        the window has not closed, so no root exists yet
    nobody visited    the window closed empty, so there is no root to publish
    not in the tree   the window had visits, but not from this wallet

A visitor whose reward was held opens the last one. Telling them "no proof"
without saying which of the three it is leaves them unable to tell a wait from
a refusal.
"""

import time

from fastapi import APIRouter, HTTPException, Path, Query

from api import epochs, merkle, subgraph
from api.schemas import EpochCommitment, EpochWindow, ScoreProof

router = APIRouter(prefix="/epochs", tags=["epochs"])


def _commitment(epoch: int) -> epochs.Commitment:
    """The closed epoch, or the reason there is nothing to hand back."""
    try:
        found = epochs.build(epoch)
    except epochs.EpochNotClosed:
        # 409 rather than 404: the resource is not missing, it is not finished.
        # Asking again after the window closes is the correct thing to do.
        raise HTTPException(409, f"Epoch {epoch} is still open") from None
    except subgraph.SubgraphError as exc:
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc

    if found is None:
        raise HTTPException(404, f"Nobody visited in epoch {epoch}, so it has no root")
    return found


@router.get("/current", response_model=EpochWindow)
def current():
    """The epoch collecting scores right now. It has no root yet, by design."""
    epoch = epochs.current_epoch()
    start, end = epochs.window(epoch)
    return EpochWindow(
        epoch=epoch,
        start=start,
        end=end,
        seconds_remaining=max(0, end - int(time.time())),
    )


@router.get("/{epoch}", response_model=EpochCommitment)
def commitment(epoch: int = Path(..., ge=0)):
    """The root over every score in a closed epoch."""
    found = _commitment(epoch)
    return EpochCommitment(
        epoch=found.epoch,
        start=found.start,
        end=found.end,
        root=found.root,
        wallets=found.wallets,
    )


@router.get("/{epoch}/proof", response_model=ScoreProof)
def proof(
    epoch: int = Path(..., ge=0),
    address: str = Query(..., pattern=r"^0x[0-9a-fA-F]{40}$"),
):
    """One wallet's committed score, with the siblings that prove it.

    The score travels with the proof because a proof alone verifies nothing:
    `verifyScore` takes the pair, and it is the pair we are held to.
    """
    found = _commitment(epoch)

    wallet = address.lower()
    score_bps = found.scores.get(wallet)
    if score_bps is None:
        raise HTTPException(404, f"{address} was not scored in epoch {epoch}")

    return ScoreProof(
        epoch=found.epoch,
        address=wallet,
        score=score_bps / merkle.SCORE_SCALE,
        score_bps=score_bps,
        root=found.root,
        proof=found.tree.proof(wallet, score_bps),
    )
