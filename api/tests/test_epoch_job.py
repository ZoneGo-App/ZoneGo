"""The hourly job, and the ways it is allowed to fail.

It runs unattended inside the API process, so the property that matters most is
not that it publishes — it is that it never takes the API down with it. A judge
opening the link during a subgraph hiccup should find a working service.
"""

import pytest

from api import epoch_job, epochs
from api.config import get_config


@pytest.fixture(autouse=True)
def fresh():
    epoch_job.reset()
    yield
    epoch_job.reset()


def test_it_closes_the_newest_finished_epoch():
    assert epoch_job.run_once() is True


def test_it_does_not_publish_the_same_epoch_twice():
    """Two roots for one hour is two answers to a question with one answer."""
    assert epoch_job.run_once() is True
    assert epoch_job.run_once() is False


def test_a_quiet_hour_publishes_nothing(monkeypatch):
    """A root over nobody is a transaction that says nothing."""
    monkeypatch.setattr(epochs, "build", lambda epoch: None)
    assert epoch_job.run_once() is False


def test_a_subgraph_failure_does_not_raise(monkeypatch):
    """The whole point of the guard: a bad hour must not kill the process."""

    def boom(epoch):
        raise RuntimeError("subgraph unavailable")

    monkeypatch.setattr(epochs, "build", boom)
    assert epoch_job.run_once() is False


def test_a_failed_hour_is_logged_with_the_reason(monkeypatch, caplog):
    def boom(epoch):
        raise RuntimeError("subgraph unavailable")

    monkeypatch.setattr(epochs, "build", boom)
    with caplog.at_level("WARNING", logger="zonego"):
        epoch_job.run_once()

    record = next(r for r in caplog.records if r.getMessage() == "epoch_failed")
    assert "subgraph unavailable" in record.error


def test_it_records_the_root_it_would_publish(caplog):
    """Until commitEpoch exists, the root has to be visible somewhere or there
    is no way to tell the job from a no-op."""
    with caplog.at_level("INFO", logger="zonego"):
        epoch_job.run_once()

    record = next(r for r in caplog.records if r.getMessage() == "epoch_ready")
    assert record.root.startswith("0x")
    assert record.published is False


def test_it_never_runs_the_open_epoch(monkeypatch):
    """Its root would change with every visit, so there is nothing to commit."""
    seen = {}

    def spy(epoch):
        seen["epoch"] = epoch
        return None

    monkeypatch.setattr(epochs, "build", spy)
    epoch_job.run_once()
    assert seen["epoch"] < epochs.current_epoch()


def test_the_tick_is_shorter_than_an_epoch():
    """Otherwise a root lands up to an hour after its window closed."""
    assert epoch_job.TICK_SECONDS < get_config().epoch_seconds
