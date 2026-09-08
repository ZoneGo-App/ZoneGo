from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_campaigns_returns_three():
    r = client.get("/campaigns")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_missing_campaign_returns_404():
    r = client.get("/campaigns/999")
    assert r.status_code == 404
