"""Guards on the settings that only bite once the service is deployed."""

import pytest

from api.config import Config, cors_origin_list, get_config


def test_cors_origins_parse_into_a_list():
    assert cors_origin_list() == ["http://localhost:3000"]


def test_cors_origins_survive_spaces_and_extra_commas(monkeypatch):
    monkeypatch.setattr(get_config(), "cors_origins", " https://a.app , https://b.app ,")
    assert cors_origin_list() == ["https://a.app", "https://b.app"]


def test_search_refuses_instead_of_answering_empty(monkeypatch):
    """The bug this guards: 200 with [] read as 'nothing nearby'.

    Which 5xx it is depends on why the subgraph is unreachable. What must never
    happen is a success with no results.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setattr(get_config(), "mock_mode", False)
    monkeypatch.setattr(get_config(), "subgraph_url", "")
    r = TestClient(app).get("/search", params={"lat": 40.719, "lon": -73.988})
    assert r.status_code >= 500
    assert r.json() != []


def test_a_url_pasted_with_a_newline_still_works():
    """The outage this guards, verbatim.

    SUBGRAPH_URL was pasted into the Render dashboard carrying a trailing
    newline. httpx raises InvalidURL for that, InvalidURL does not inherit from
    httpx.HTTPError, so the handler that turns an upstream failure into a 502
    never saw it — and every route reading the index answered 500 instead. The
    setting was one invisible character wrong and the service looked broken.
    """
    url = "https://api.studio.thegraph.com/query/1758817/zone-go/v0.0.2"
    for dirty in (url + "\n", " " + url, f'"{url}"', f"  {url}  \n"):
        assert Config(subgraph_url=dirty).subgraph_url == url


def test_a_malformed_url_is_an_upstream_failure_not_a_crash(monkeypatch):
    """Belt and braces: if something still slips past the trim, it is a 502.

    A 500 tells whoever is on call that our code broke. A 502 naming the
    setting tells them which value to fix.
    """
    from api import subgraph

    monkeypatch.setattr(get_config(), "subgraph_url", "https://example.test/\ngql")
    subgraph.clear_cache()
    with pytest.raises(subgraph.SubgraphError):
        subgraph.list_campaigns()
    subgraph.clear_cache()
