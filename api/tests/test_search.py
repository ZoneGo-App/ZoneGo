from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# Standing on Delancey Street, Lower East Side.
HERE = {"lat": 40.7190, "lon": -73.9882}


def test_search_without_query_returns_everything_nearby():
    r = client.get("/search", params={**HERE, "radius_km": 1})
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_bodega_shows_up_for_sneakers():
    """The whole pitch: Google files it as a corner store and hides it."""
    r = client.get("/search", params={**HERE, "q": "sneakers", "radius_km": 1})
    names = [h["campaign"]["merchant_name"] for h in r.json()]
    assert "Delancey Bodega" in names


def test_every_word_has_to_match():
    r = client.get("/search", params={**HERE, "q": "vintage sneakers", "radius_km": 1})
    names = [h["campaign"]["merchant_name"] for h in r.json()]
    assert names == ["Orchard Street Kicks"]


def test_results_come_back_nearest_first():
    r = client.get("/search", params={**HERE, "radius_km": 10})
    distances = [h["distance_meters"] for h in r.json()]
    assert distances == sorted(distances)


def test_radius_actually_excludes():
    far = {"lat": 40.8500, "lon": -73.9000}
    r = client.get("/search", params={**far, "radius_km": 1})
    assert r.json() == []


def test_unknown_radius_falls_back_to_one_km():
    r = client.get("/search", params={**HERE, "radius_km": 7})
    assert r.status_code == 200
