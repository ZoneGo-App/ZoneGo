import httpx
import pytest
from fastapi.testclient import TestClient

from api import subgraph
from api.config import get_config
from api.main import app

client = TestClient(app)


def test_explorers_come_back_ranked():
    rows = client.get("/leaderboard").json()
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    visits = [r["visits"] for r in rows]
    assert visits == sorted(visits, reverse=True)


def test_merchants_are_a_separate_table():
    rows = client.get("/leaderboard", params={"scope": "merchants"}).json()
    assert rows[0]["visits"] == 412
    # Only explorers carry the distinct-stores column.
    assert rows[0]["distinct_merchants"] is None


def test_explorers_carry_distinct_stores():
    rows = client.get("/leaderboard").json()
    assert all(r["distinct_merchants"] is not None for r in rows)


def test_an_unknown_scope_is_refused():
    r = client.get("/leaderboard", params={"scope": "everyone"})
    assert r.status_code == 422


def test_limit_is_respected():
    rows = client.get("/leaderboard", params={"limit": 2}).json()
    assert len(rows) == 2


def test_a_broken_subgraph_is_not_an_empty_table(monkeypatch):
    """An empty leaderboard reads as 'nobody played yet'. Very different."""
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(get_config(), "subgraph_url", "https://example.test/gql")
    subgraph.clear_cache()

    def broken(url, **kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "post", broken)
    assert client.get("/leaderboard").status_code == 502
    subgraph.clear_cache()


def test_live_visitors_are_ranked_from_the_subgraph(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(get_config(), "subgraph_url", "https://example.test/gql")
    subgraph.clear_cache()

    payload = {
        "data": {
            "visitors": [
                {"id": "0x" + "a1" * 20, "visitCount": 12, "distinctMerchants": 5},
                {"id": "0x" + "b2" * 20, "visitCount": 3, "distinctMerchants": 2},
            ]
        }
    }
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, json=payload, request=httpx.Request("POST", url)
        ),
    )

    rows = client.get("/leaderboard").json()
    assert rows[0]["visits"] == 12
    assert rows[0]["label"].startswith("0xa1a1")
    assert rows[1]["rank"] == 2
    subgraph.clear_cache()
