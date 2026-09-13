"""The hourly job that closes an epoch and publishes its root.

An epoch only means something once it is on chain. Until then it is a number we
computed and could recompute differently, which is exactly the position the
Merkle root exists to get us out of. So something has to run every hour without
anyone asking it to, and this is that something.

It lives inside the API process rather than as its own service, and that is a
deliberate trade. A second container is a second thing to deploy, a second thing
to keep funded, and a second thing to notice has died — for a job that runs once
an hour and finishes in seconds. The cost is that two replicas would both try to
publish; the guard for that is on chain, where `commitEpoch` refuses an epoch
that is not greater than the one already committed.

It never raises. A background task that kills the process on a bad hour would
take the whole API down over a subgraph hiccup, and the API is the part a judge
opens.
"""

import asyncio
import time

from api import epochs, observability, oracle
from api.config import get_config

# Checked more often than an epoch is long, so the root lands soon after the
# window closes rather than up to an hour late.
TICK_SECONDS = 60

_last_published: int | None = None


def reset() -> None:
    global _last_published
    _last_published = None


def _settled(fields: dict, reason: str) -> bool:
    """Nothing left to do for this epoch, and it is not a failure."""
    observability.log.info(
        "epoch_ready", extra={**fields, "published": False, "reason": reason}
    )
    return True


def _publish(commitment: epochs.Commitment) -> bool:
    """Put the root on chain. True when the epoch needs no further attempt.

    False is reserved for a node that refused or could not be reached — the
    caller leaves the epoch unmarked so the next tick tries again, because an
    hour's root should not be lost to one bad minute. Every other outcome,
    including having nothing to publish to, is settled and says so in the log.
    """
    fields = {
        "epoch": commitment.epoch,
        "root": commitment.root,
        "wallets": commitment.wallets,
    }

    if get_config().mock_mode:
        return _settled(fields, "mock mode, no chain to publish to")
    if not oracle.configured():
        return _settled(fields, "FraudOracle address or operator key not set")

    try:
        on_chain = oracle.published_epoch()
        if on_chain is not None and commitment.epoch <= on_chain:
            # The job's memory dies with the process, so after a redeploy it
            # reaches an hour the chain already answered. Two replicas would
            # race here too. Neither is a failure.
            return _settled(fields, f"already on chain, at epoch {on_chain}")

        tx_hash = oracle.commit_epoch(root=commitment.root, epoch=commitment.epoch)
    except oracle.OracleError as exc:
        observability.log.warning(
            "epoch_publish_failed", extra={**fields, "error": str(exc)}
        )
        return False

    observability.log.info(
        "epoch_ready", extra={**fields, "published": True, "tx_hash": tx_hash}
    )
    return True


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

    if commitment is None:
        # A quiet hour. Committing a root over nobody would be a transaction
        # that says nothing, so there is nothing to publish and that is fine.
        _last_published = epoch
        observability.log.info("epoch_empty", extra={"epoch": epoch})
        return False

    if not _publish(commitment):
        # Left unmarked on purpose, so the next tick retries this same hour.
        return False

    _last_published = epoch
    return True


async def loop() -> None:
    config = get_config()
    observability.log.info(
        "epoch_job_started", extra={"every_seconds": config.epoch_seconds}
    )
    while True:
        started = time.monotonic()
        try:
            # In a worker thread: the subgraph and node calls inside are
            # blocking, and this coroutine shares the event loop with every
            # request. Called inline, a slow index froze the whole API for as
            # long as the call took — every minute, if the node was failing.
            await asyncio.to_thread(run_once)
        except Exception as exc:  # noqa: BLE001
            observability.log.warning("epoch_tick_failed", extra={"error": str(exc)})
        await asyncio.sleep(max(1.0, TICK_SECONDS - (time.monotonic() - started)))
