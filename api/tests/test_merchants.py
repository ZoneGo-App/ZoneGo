"""A store's own name, and the fence that keeps anyone else from setting it.

Before this, every campaign reached the map as "Merchant 0xd17c…9db4". The name
now comes from a profile the merchant signs — and the tests that matter most
are the ones where somebody who is not the merchant tries.
"""

import time

import httpx
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

from api import profiles, subgraph
from api.config import get_config
from api.eip712 import geohash_to_bytes32
from api.main import app

client = TestClient(app)

# Keys that exist only here.
MERCHANT = Account.from_key("0x" + "22" * 32)
STRANGER = Account.from_key("0x" + "33" * 32)


def signed(account, *, wallet=None, name="Delancey Bodega", description="coffee, sneakers",
           issued_at=None):
    wallet = wallet or account.address
    issued_at = issued_at if issued_at is not None else int(time.time())
    text = profiles.message(wallet=wallet, name=name, description=description, issued_at=issued_at)
    signature = account.sign_message(encode_defunct(text=text)).signature.hex()
    return {
        "wallet": wallet,
        "name": name,
        "description": description,
        "issued_at": issued_at,
        "signature": "0x" + signature.removeprefix("0x"),
    }


# --- saving -----------------------------------------------------------------


def test_a_merchant_names_their_own_store():
    r = client.post("/merchants/profile", json=signed(MERCHANT))
    assert r.status_code == 200, r.text

    back = client.get(f"/merchants/profile/{MERCHANT.address}")
    assert back.status_code == 200
    assert back.json()["name"] == "Delancey Bodega"
    assert back.json()["description"] == "coffee, sneakers"


def test_nobody_can_rename_somebody_elses_store():
    """The request this endpoint exists to refuse.

    A stranger signs with their own key but names the merchant's wallet. Without
    the signature check this would put "CLOSED" on a store that is open.
    """
    attack = signed(STRANGER, wallet=MERCHANT.address, name="CLOSED — do not come")
    r = client.post("/merchants/profile", json=attack)
    assert r.status_code == 401
    assert client.get(f"/merchants/profile/{MERCHANT.address}").status_code == 404


def test_a_signature_does_not_cover_a_different_name():
    body = signed(MERCHANT, name="Delancey Bodega")
    body["name"] = "Somebody Else's Name"
    assert client.post("/merchants/profile", json=body).status_code == 401


def test_a_signature_from_long_ago_is_refused():
    old = int(time.time()) - get_config().merchant_profile_signature_window_seconds - 60
    assert client.post("/merchants/profile", json=signed(MERCHANT, issued_at=old)).status_code == 401


def test_an_old_signed_profile_cannot_put_back_a_name_that_changed():
    """Replay. The earlier request is still inside its window, and still signed."""
    now = int(time.time())
    first = signed(MERCHANT, name="Old Name", issued_at=now - 30)
    second = signed(MERCHANT, name="New Name", issued_at=now)

    assert client.post("/merchants/profile", json=first).status_code == 200
    assert client.post("/merchants/profile", json=second).status_code == 200
    assert client.post("/merchants/profile", json=first).status_code == 409
    assert client.get(f"/merchants/profile/{MERCHANT.address}").json()["name"] == "New Name"


def test_a_name_that_spans_lines_is_refused():
    """A line break could move text between two signed fields."""
    body = signed(MERCHANT, name="Bodega\nDescription: fake")
    assert client.post("/merchants/profile", json=body).status_code == 422


def test_a_description_typed_on_several_lines_is_accepted():
    """The merchant writes it in a multi-line box and presses Enter.

    Refusing that failed the save — and the frontend does not surface errors, so
    the store would have kept its address with nobody knowing why.
    """
    body = signed(MERCHANT, description="Sneakers.\nSportswear.\nBackpacks.")
    assert client.post("/merchants/profile", json=body).status_code == 200


def test_a_signature_cannot_be_reread_with_the_text_split_differently():
    """Why line breaks are safe in the description and not in the name.

    The merchant signs a description that happens to contain what looks like a
    timestamp line. Resent with that fake line moved into the timestamp, the
    values differ but an attacker would want the same message to match. The
    timestamp is an integer, so there is no split that works.
    """
    now = int(time.time())
    body = signed(MERCHANT, description=f"shoes\nIssued at: {now - 1}", issued_at=now)
    assert client.post("/merchants/profile", json=body).status_code == 200

    # 401 and nothing else. A 409 would mean the signature matched and only the
    # timestamp check stopped it — which is the hole this test is here to rule out.
    reread = {**body, "description": "shoes", "issued_at": now - 1}
    assert client.post("/merchants/profile", json=reread).status_code == 401


def test_an_unknown_wallet_has_no_profile():
    assert client.get(f"/merchants/profile/{STRANGER.address}").status_code == 404


# --- where the name shows up ------------------------------------------------


@pytest.fixture
def live_index(monkeypatch):
    """One funded campaign on Delancey, owned by the test merchant."""
    config = get_config()
    monkeypatch.setattr(config, "mock_mode", False)
    monkeypatch.setattr(config, "subgraph_url", "https://example.test/gql")
    subgraph.clear_cache()

    node = {
        "id": "0x01",
        "campaignId": "1",
        "merchant": {"id": MERCHANT.address.lower()},
        "rewardPerVisit": "50000",
        "dailyCap": "50",
        "geohash": geohash_to_bytes32("dr5rsked"),
        "radiusMeters": "120",
        "balance": "20000000",
        "active": True,
        "createdAt": "1789185856",
        "visitCount": 0,
        "totalPaid": "0",
    }

    def fake_post(url, **kwargs):
        return httpx.Response(200, json={"data": {"campaigns": [node]}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    yield
    subgraph.clear_cache()


def test_without_a_profile_the_store_keeps_its_address(live_index):
    name = client.get("/campaigns").json()[0]["merchant_name"]
    assert name.startswith("Merchant 0x")


def test_the_name_replaces_the_address_everywhere(live_index):
    client.post("/merchants/profile", json=signed(MERCHANT, name="Kim's Sneakers"))

    assert client.get("/campaigns").json()[0]["merchant_name"] == "Kim's Sneakers"

    hits = client.get("/search", params={"lat": 40.7185, "lon": -73.988, "radius_km": 1}).json()
    assert hits[0]["campaign"]["merchant_name"] == "Kim's Sneakers"


def test_the_description_is_what_search_finds(live_index):
    """The README's own example, working on real data.

    Nothing on chain mentions a shoe. The merchant said so, and now somebody
    typing "sneakers" finds the store.
    """
    params = {"lat": 40.7185, "lon": -73.988, "radius_km": 1, "q": "sneakers"}
    assert client.get("/search", params=params).json() == []

    client.post("/merchants/profile",
                json=signed(MERCHANT, name="Delancey Bodega", description="coffee, running sneakers"))
    hits = client.get("/search", params=params).json()
    assert len(hits) == 1
    assert hits[0]["campaign"]["sells"] == "coffee, running sneakers"


def test_storage_that_cannot_be_read_does_not_take_search_down(live_index, monkeypatch, tmp_path):
    """A label is not worth an outage: the store shows its address instead."""
    monkeypatch.setattr(get_config(), "merchant_profiles_path", str(tmp_path / "missing" / "x.db"))
    r = client.get("/search", params={"lat": 40.7185, "lon": -73.988, "radius_km": 1})
    assert r.status_code == 200
    assert r.json()[0]["campaign"]["merchant_name"].startswith("Merchant 0x")
