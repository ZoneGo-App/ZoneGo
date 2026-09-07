"""Epochs, and the promise a root is supposed to keep.

The property under test is one sentence: anyone can rebuild the same root from
public data, and a wallet can prove the score inside it. Everything below is
that sentence taken apart — determinism, the window boundaries, and the three
different reasons a proof can be unavailable.
"""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from api import epochs, merkle, subgraph
from api.config import get_config
from api.main import app
from api.mock_data import MOCK_EXPLORERS

client = TestClient(app)

WALLET = MOCK_EXPLORERS[0].address
STRANGER = "0xDEADBEEF00000000000000000000000000000001"


def closed() -> int:
    return epochs.current_epoch() - 1


@pytest.fixture
def live(monkeypatch):
    """Live mode with a subgraph that answers whatever the test hands it."""
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(get_config(), "subgraph_url", "https://example.test/gql")
    subgraph.clear_cache()
    yield
    subgraph.clear_cache()


def answer(monkeypatch, payload):
    def fake_post(url, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)


def visits_of(*addresses):
    return {"data": {"visits": [{"visitor": {"id": a.lower()}} for a in addresses]}}


# --- numbering -------------------------------------------------------------


def test_the_epoch_number_is_the_clock_divided_by_the_window():
    size = get_config().epoch_seconds
    assert epochs.epoch_at(0) == 0
    assert epochs.epoch_at(size - 1) == 0
    assert epochs.epoch_at(size) == 1


def test_windows_are_half_open_and_leave_no_gap():
    """A visit on a boundary belongs to exactly one epoch, never both or neither."""
    start, end = epochs.window(41)
    next_start, _ = epochs.window(42)
    assert end == next_start
    assert epochs.epoch_at(start) == 41
    assert epochs.epoch_at(end) == 42


def test_the_current_epoch_holds_the_current_time():
    assert epochs.epoch_at(int(time.time())) == epochs.current_epoch()


# --- building --------------------------------------------------------------


def test_the_open_epoch_cannot_be_committed():
    """Its root would change with every visit, so there is nothing to publish."""
    with pytest.raises(epochs.EpochNotClosed):
        epochs.build(epochs.current_epoch())


def test_a_future_epoch_cannot_be_committed_either():
    with pytest.raises(epochs.EpochNotClosed):
        epochs.build(epochs.current_epoch() + 5)


def test_a_closed_epoch_rebuilds_to_the_same_root():
    """The whole argument: no cache, no state, same answer for anyone who asks."""
    first = epochs.build(closed())
    epochs.clear_cache()
    second = epochs.build(closed())
    assert first.root == second.root
    assert first.scores == second.scores


def test_an_empty_epoch_has_no_root_rather_than_an_empty_one(live, monkeypatch):
    """A quiet hour is not a tree over nothing — it is nothing to commit."""
    answer(monkeypatch, {"data": {"visits": []}})
    assert epochs.build(closed()) is None


def test_scores_are_committed_in_basis_points():
    commitment = epochs.build(closed())
    for value in commitment.scores.values():
        assert isinstance(value, int)
        assert 0 <= value <= merkle.SCORE_SCALE


def test_a_wallet_that_did_not_visit_has_no_proof():
    assert epochs.proof_for(closed(), STRANGER) is None


def test_the_proof_verifies_against_the_root():
    commitment = epochs.build(closed())
    score_bps, proof = epochs.proof_for(closed(), WALLET.lower())
    assert merkle.verify(commitment.root, WALLET, score_bps, proof)


# --- the endpoints ---------------------------------------------------------


def test_current_reports_a_window_that_has_not_closed():
    body = client.get("/epochs/current").json()
    assert body["epoch"] == epochs.current_epoch()
    assert body["end"] > body["start"]
    assert 0 < body["seconds_remaining"] <= get_config().epoch_seconds


def test_asking_for_the_open_epoch_is_a_conflict_not_a_miss():
    """404 would read as 'never existed'; this one exists and is not ready."""
    response = client.get(f"/epochs/{epochs.current_epoch()}")
    assert response.status_code == 409
    assert "still open" in response.json()["detail"]


def test_a_closed_epoch_returns_its_root():
    body = client.get(f"/epochs/{closed()}").json()
    assert body["root"].startswith("0x")
    assert len(body["root"]) == 66
    assert body["wallets"] == len(MOCK_EXPLORERS)


def test_a_root_is_not_claimed_to_be_on_chain():
    """commitEpoch is still `revert("not implemented")`. Saying otherwise here
    would be the one lie this endpoint exists to prevent."""
    assert client.get(f"/epochs/{closed()}").json()["committed"] is False


def test_the_endpoint_hands_back_a_proof_that_verifies():
    body = client.get(f"/epochs/{closed()}/proof", params={"address": WALLET}).json()
    assert merkle.verify(body["root"], WALLET, body["score_bps"], body["proof"])


def test_the_readable_score_and_the_contract_score_agree():
    body = client.get(f"/epochs/{closed()}/proof", params={"address": WALLET}).json()
    assert body["score_bps"] == round(body["score"] * merkle.SCORE_SCALE)


def test_the_address_comes_back_however_it_was_typed():
    """Checksummed in, lowercase out — the frontend has to be able to match it."""
    body = client.get(f"/epochs/{closed()}/proof", params={"address": WALLET}).json()
    assert body["address"] == WALLET.lower()


def test_an_unscored_wallet_gets_a_miss_not_a_zero():
    """A score of zero is a judgement about someone. Never having been looked at
    is not, and a person appealing a held reward has to be able to tell them
    apart."""
    response = client.get(f"/epochs/{closed()}/proof", params={"address": STRANGER})
    assert response.status_code == 404
    assert "not scored" in response.json()["detail"]


def test_a_malformed_address_is_rejected_before_any_query():
    assert client.get(f"/epochs/{closed()}/proof", params={"address": "0x1"}).status_code == 422


def test_a_negative_epoch_is_rejected():
    assert client.get("/epochs/-1").status_code == 422


def test_an_empty_epoch_says_so(live, monkeypatch):
    answer(monkeypatch, {"data": {"visits": []}})
    response = client.get(f"/epochs/{closed()}")
    assert response.status_code == 404
    assert "Nobody visited" in response.json()["detail"]


def test_an_index_outage_is_never_an_empty_epoch(live, monkeypatch):
    """The failure that matters: an outage read as 'nobody came' would commit a
    root over an hour that actually had visits in it."""
    answer(monkeypatch, {"errors": [{"message": "store not indexed"}]})
    assert client.get(f"/epochs/{closed()}").status_code == 502


def test_a_live_epoch_is_built_from_the_indexed_visitors(live, monkeypatch):
    answer(monkeypatch, visits_of(WALLET, STRANGER, WALLET))
    body = client.get(f"/epochs/{closed()}").json()
    # The same wallet twice in one window is one leaf, not two.
    assert body["wallets"] == 2
