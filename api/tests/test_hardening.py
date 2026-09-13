"""Rate limits, rejection records, and what the service says about itself.

The property these protect is narrow and worth stating: a loop against
`/visits/claim` should stop costing us gas before it empties the relay wallet,
and when a merchant asks why nobody got paid this afternoon there should be an
answer grouped by reason rather than a scroll of prose.
"""

import pytest
from fastapi.testclient import TestClient

from api import observability, ratelimit
from api.config import get_config
from api.main import app

client = TestClient(app)

A_CLAIM = {
    "campaign_id": 1,
    "nonce": 1,
    "expiry": 1,  # already past, so it is refused before anything costs
    "geohash": "0x" + "00" * 32,
    "signature": "0x" + "11" * 65,
    "visitor": "0x7A3c9E1b4D2f5A8c6B0e9F7d3C1a5B8e2D4f6A90",
}


# --- rate limits ------------------------------------------------------------


def test_the_claim_route_is_the_strictest():
    """It is the only one where each call can spend our own ETH."""
    claim = ratelimit.limit_for("/visits/claim")
    search = ratelimit.limit_for("/search")
    assert claim[0] < search[0]


def test_a_loop_against_claim_is_cut_off():
    calls, _ = ratelimit.limit_for("/visits/claim")
    for _ in range(calls):
        client.post("/visits/claim", json=A_CLAIM)

    r = client.post("/visits/claim", json=A_CLAIM)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_reads_are_not_throttled_at_the_same_rate():
    """A search is a cached read. Throttling it like a claim punishes browsing."""
    for _ in range(20):
        assert client.get("/campaigns").status_code == 200


def test_routes_have_separate_budgets():
    """Spending the claim allowance should not close the door on searching."""
    calls, _ = ratelimit.limit_for("/visits/claim")
    for _ in range(calls + 2):
        client.post("/visits/claim", json=A_CLAIM)

    assert client.get("/campaigns").status_code == 200


def test_ids_in_the_path_share_one_budget():
    """Otherwise walking `/campaigns/1`, `/campaigns/2`… never hits a limit."""
    assert ratelimit._bucket("/campaigns/1") == ratelimit._bucket("/campaigns/2")


def test_two_people_behind_the_same_proxy_get_separate_budgets():
    """Render hands every request over from one address. Keying on that address
    would make one budget for everyone using the app."""
    calls, _ = ratelimit.limit_for("/visits/claim")
    first = {"X-Forwarded-For": "203.0.113.1"}
    for _ in range(calls):
        client.post("/visits/claim", json=A_CLAIM, headers=first)

    blocked = client.post("/visits/claim", json=A_CLAIM, headers=first)
    someone_else = client.post(
        "/visits/claim", json=A_CLAIM, headers={"X-Forwarded-For": "203.0.113.2"}
    )
    assert blocked.status_code == 429
    assert someone_else.status_code != 429


def test_the_first_forwarded_address_is_the_client():
    """Render puts the real client first; anything after it is a proxy hop."""
    assert ratelimit.client_key("203.0.113.7, 10.0.0.1", "10.0.0.2") == "203.0.113.7"


def test_without_a_proxy_the_connection_address_is_the_client():
    assert ratelimit.client_key(None, "127.0.0.1") == "127.0.0.1"
    assert ratelimit.client_key("  ", "127.0.0.1") == "127.0.0.1"


def test_health_is_never_throttled():
    """Going blind exactly when a service is under load is the wrong failure."""
    for _ in range(200):
        assert client.get("/health").status_code == 200


# --- the record of a rejection ----------------------------------------------


def test_a_refused_claim_is_counted_by_reason():
    client.post("/visits/claim", json=A_CLAIM)
    counts = client.get("/metrics").json()["rejected_claims"]
    assert counts.get("signature_expired") == 1


def test_reasons_are_slugs_not_sentences():
    """They are what you group by, so they have to be stable and short."""
    client.post("/visits/claim", json=A_CLAIM)
    for reason in client.get("/metrics").json()["rejected_claims"]:
        assert " " not in reason


def test_a_rate_limited_call_is_recorded_too():
    calls, _ = ratelimit.limit_for("/visits/claim")
    for _ in range(calls + 1):
        client.post("/visits/claim", json=A_CLAIM)

    assert client.get("/metrics").json()["rejected_claims"].get("rate_limited", 0) >= 1


def test_responses_are_tallied_by_class():
    client.get("/campaigns")
    client.get("/campaigns/999")
    responses = client.get("/metrics").json()["responses"]
    assert responses.get("2xx", 0) >= 1
    assert responses.get("4xx", 0) >= 1


def test_the_log_line_carries_the_campaign_and_the_reason(caplog):
    """A count says how many. The line says which one, so it can be chased."""
    with caplog.at_level("WARNING", logger="zonego"):
        client.post("/visits/claim", json=A_CLAIM)

    record = next(r for r in caplog.records if r.getMessage() == "claim_rejected")
    assert record.reason == "signature_expired"
    assert record.campaign_id == 1


# --- readiness --------------------------------------------------------------


def test_health_says_up_without_claiming_anything_else():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "mock_mode" in body


def test_mock_mode_is_ready_without_a_node_or_an_index():
    """Nothing external is required, so reporting a problem would be a false
    alarm on a service configured exactly as intended."""
    body = client.get("/ready").json()
    assert body["ready"] is True
    assert body["mock_mode"] is True


def test_live_mode_reports_what_is_missing(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)
    checks = client.get("/ready").json()["checks"]
    assert checks["subgraph"] == "missing"
    assert checks["relay_key"] == "missing"
    assert checks["attester_key"] == "missing"


def test_not_ready_when_the_index_and_node_are_unreachable(monkeypatch):
    monkeypatch.setattr(get_config(), "mock_mode", False)
    assert client.get("/ready").json()["ready"] is False


def test_metrics_reports_uptime():
    assert client.get("/metrics").json()["uptime_seconds"] >= 0
