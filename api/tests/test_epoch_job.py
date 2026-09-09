"""The hourly job, and the ways it is allowed to fail.

It runs unattended inside the API process, so the property that matters most is
not that it publishes — it is that it never takes the API down with it. A judge
opening the link during a subgraph hiccup should find a working service.
"""

import pytest

from api import epoch_job, epochs, oracle
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


def test_it_records_the_root_even_with_no_chain_to_publish_to(caplog):
    """Against the samples there is nothing to commit to, but the root still
    has to be visible somewhere or there is no telling the job from a no-op."""
    with caplog.at_level("INFO", logger="zonego"):
        epoch_job.run_once()

    record = next(r for r in caplog.records if r.getMessage() == "epoch_ready")
    assert record.root.startswith("0x")
    assert record.published is False
    assert "mock mode" in record.reason


@pytest.fixture
def live(monkeypatch):
    """Live mode with an oracle that is wired up and answers.

    The wallet source is stubbed because out of mock mode it reaches for the
    subgraph, and what these tests are about is what happens after the tree is
    built, not where the names came from.
    """
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(
        epochs, "wallets_in", lambda start, end: ["0x" + "a1" * 20, "0x" + "b2" * 20]
    )
    monkeypatch.setattr(oracle, "configured", lambda: True)
    monkeypatch.setattr(oracle, "published_epoch", lambda: None)


def test_it_publishes_the_root_and_records_the_transaction(live, monkeypatch, caplog):
    monkeypatch.setattr(oracle, "commit_epoch", lambda **kw: "0x" + "cd" * 32)
    with caplog.at_level("INFO", logger="zonego"):
        assert epoch_job.run_once() is True

    record = next(r for r in caplog.records if r.getMessage() == "epoch_ready")
    assert record.published is True
    assert record.tx_hash == "0x" + "cd" * 32


def test_it_does_not_republish_what_the_chain_already_has(live, monkeypatch, caplog):
    """After a redeploy the job reaches an hour the chain already answered."""
    monkeypatch.setattr(oracle, "published_epoch", lambda: epochs.current_epoch())

    def never(**kw):
        raise AssertionError("commit_epoch must not be called")

    monkeypatch.setattr(oracle, "commit_epoch", never)
    with caplog.at_level("INFO", logger="zonego"):
        assert epoch_job.run_once() is True

    record = next(r for r in caplog.records if r.getMessage() == "epoch_ready")
    assert record.published is False
    assert "already on chain" in record.reason


def test_an_unreachable_node_leaves_the_epoch_for_the_next_tick(live, monkeypatch):
    """One bad minute must not cost an hour's root.

    The epoch stays unmarked, so the tick a minute later tries the same one
    again instead of moving on and losing it until a restart.
    """
    attempts = []

    def flaky(**kw):
        attempts.append(kw["epoch"])
        if len(attempts) == 1:
            raise oracle.OracleError("node unreachable")
        return "0x" + "cd" * 32

    monkeypatch.setattr(oracle, "commit_epoch", flaky)

    assert epoch_job.run_once() is False
    assert epoch_job.run_once() is True
    assert attempts[0] == attempts[1]


def test_a_publish_failure_is_logged_with_the_reason(live, monkeypatch, caplog):
    def boom(**kw):
        raise oracle.OracleError("node unreachable")

    monkeypatch.setattr(oracle, "commit_epoch", boom)
    with caplog.at_level("WARNING", logger="zonego"):
        epoch_job.run_once()

    record = next(r for r in caplog.records if r.getMessage() == "epoch_publish_failed")
    assert "node unreachable" in record.error


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
