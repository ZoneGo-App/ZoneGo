"""Guards on the two settings that only bite once the service is deployed."""

from api.config import cors_origin_list, get_config


def test_cors_origins_parse_into_a_list():
    assert cors_origin_list() == ["http://localhost:3000"]


def test_cors_origins_survive_spaces_and_extra_commas(monkeypatch):
    monkeypatch.setattr(get_config(), "cors_origins", " https://a.app , https://b.app ,")
    assert cors_origin_list() == ["https://a.app", "https://b.app"]


def test_search_refuses_instead_of_answering_empty(monkeypatch):
    """The bug this replaced: 200 with [] looked like 'nothing nearby'."""
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setattr(get_config(), "mock_mode", False)
    r = TestClient(app).get("/search", params={"lat": 40.719, "lon": -73.988})
    assert r.status_code == 501
