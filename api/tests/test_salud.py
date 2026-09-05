from fastapi.testclient import TestClient

from api.main import app

cliente = TestClient(app)


def test_salud_responde_ok():
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_campanas_devuelve_tres():
    r = cliente.get("/campanas")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_campana_inexistente_da_404():
    r = cliente.get("/campanas/999")
    assert r.status_code == 404
