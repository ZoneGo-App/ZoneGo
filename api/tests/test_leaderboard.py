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


def test_a_zone_narrows_the_table():
    everyone = client.get("/leaderboard").json()
    les = client.get("/leaderboard", params={"zone": "dr5rsk"}).json()
    assert 0 < len(les) < len(everyone)
    assert all(r["zone"] == "dr5rsk" for r in les)


def test_the_zone_comes_back_with_a_readable_name():
    rows = client.get("/leaderboard", params={"zone": "dr5rsk"}).json()
    assert rows[0]["zone_name"] == "Lower East Side"


def test_a_zone_that_is_not_a_geohash_is_refused():
    # 'a', 'i', 'l' and 'o' are not in the geohash alphabet.
    assert client.get("/leaderboard", params={"zone": "drailo"}).status_code == 422
    assert client.get("/leaderboard", params={"zone": "dr5r"}).status_code == 422


def test_explorers_carry_points_and_merchants_do_not():
    explorers = client.get("/leaderboard").json()
    merchants = client.get("/leaderboard", params={"scope": "merchants"}).json()
    assert all(r["points"] is not None for r in explorers)
    # A merchant does not play the game — they are the board.
    assert all(r["points"] is None for r in merchants)


def test_points_follow_the_rule():
    """Five a visit, five more per store discovered."""
    row = client.get("/leaderboard").json()[0]
    assert row["points"] == row["visits"] * 5 + row["distinct_merchants"] * 5


def test_a_week_snaps_to_monday():
    rows = client.get("/leaderboard", params={"week": 1_789_000_000}).json()
    from datetime import datetime, timezone

    start = datetime.fromtimestamp(rows[0]["week_start"], tz=timezone.utc)
    assert start.weekday() == 0


def test_no_week_means_the_all_time_table():
    assert client.get("/leaderboard").json()[0]["week_start"] is None


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
