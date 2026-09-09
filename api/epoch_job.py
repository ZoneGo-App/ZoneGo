"""The hourly job that closes an epoch and publishes its root.

An epoch only means something once it is on chain. Until then it is a number we
computed and could recompute differently, which is exactly the position the
Merkle root exists to get us out of. So something has to run every hour without
anyone asking it to, and this is that something.

It lives inside the API process rather than as its own service, and that is a
deliberate trade. A second container is a second thing to deploy, a second thing
to keep funded, and a second thing to notice has died — for a job that runs once
an hour and finishes in seconds. The cost is that two replicas would both try to
publish; the guard for that is on chain, where `commitEpoch` should reject an
epoch that already has a root.

It never raises. A background task that kills the process on a bad hour would
take the whole API down over a subgraph hiccup, and the API is the part a judge
opens.
"""

import asyncio
import time

from api import epochs, observability
from api.config import get_config

# Checked more often than an epoch is long, so the root lands soon after the
# window closes rather than up to an hour late.
TICK_SECONDS = 60

_last_published: int | None = None


def reset() -> None:
    global _last_published
    _last_published = None


def _publish(commitment: epochs.Commitment) -> None:
    """Put the root on chain.

    Not wired yet: `FraudOracle.commitEpoch` is still `revert("not
    implemented")`. Until it lands, the job proves the rest of the path — the
    window closes, the subgraph is read, the tree is built — and records the
    root it would have published, so the day the contract is ready this is one
    call rather than a new feature.
    """
    observability.log.info(
        "epoch_ready",
        extra={
            "epoch": commitment.epoch,
            "root": commitment.root,
            "wallets": commitment.wallets,
            "published": False,
            "reason": "commitEpoch not implemented yet",
        },
    )


def run_once() -> bool:
    """Close the newest finished epoch, if it has not been done already."""
    global _last_published

    epoch = epochs.current_epoch() - 1
    if _last_published is not None and epoch <= _last_published:
        return False

    try:
        commitment = epochs.build(epoch)
    except epochs.EpochNotClosed:
        return False
    except Exception as exc:  # noqa: BLE001 — see the module docstring
        observability.log.warning(
            "epoch_failed", extra={"epoch": epoch, "error": str(exc)}
        )
        return False

    _last_published = epoch

    if commitment is None:
        # A quiet hour. Committing a root over nobody would be a transaction
        # that says nothing, so there is nothing to publish and that is fine.
        observability.log.info("epoch_empty", extra={"epoch": epoch})
        return False

    _publish(commitment)
    return True


async def loop() -> None:
    config = get_config()
    observability.log.info(
        "epoch_job_started", extra={"every_seconds": config.epoch_seconds}
    )
    while True:
        started = time.monotonic()
        try:
            run_once()
        except Exception as exc:  # noqa: BLE001
            observability.log.warning("epoch_tick_failed", extra={"error": str(exc)})
        await asyncio.sleep(max(1.0, TICK_SECONDS - (time.monotonic() - started)))
