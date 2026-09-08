from fastapi.testclient import TestClient

from api.config import get_config
from api.main import app

client = TestClient(app)

VISITOR = "0x" + "a1" * 20


def ask(visitor=VISITOR, campaign_id=1):
    return client.post("/score", json={"visitor": visitor, "campaign_id": campaign_id})


def test_score_is_a_probability():
    body = ask().json()
    assert 0 <= body["score"] <= 1


def test_decision_follows_the_threshold():
    body = ask().json()
    expected = "hold" if body["score"] >= body["threshold"] else "pay"
    assert body["decision"] == expected


def test_three_features_come_back_with_the_score():
    """The Graph asks for the reasoning, not just the number."""
    features = ask().json()["top_features"]
    assert len(features) == 3
    assert all(f["name"] and "weight" in f for f in features)


def test_features_are_ordered_by_weight():
    weights = [f["weight"] for f in ask().json()["top_features"]]
    assert weights == sorted(weights, reverse=True)


def test_the_same_wallet_always_scores_the_same():
    assert ask().json()["score"] == ask().json()["score"]


def test_different_wallets_score_differently():
    other = "0x" + "c3" * 20
    assert ask().json()["score"] != ask(visitor=other).json()["score"]


def test_threshold_comes_from_config():
    assert ask().json()["threshold"] == get_config().fraud_threshold


def test_a_malformed_address_is_refused():
    assert ask(visitor="nope").status_code == 422
