import time

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_sign_returns_a_payload_for_a_real_campaign():
    r = client.post("/qr/sign", json={"campaign_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["typed_data"]["primaryType"] == "VisitSig"
    assert body["typed_data"]["domain"]["chainId"] == 84532


def test_type_matches_the_contract_typehash():
    """Guards the one string that has to be identical in VisitRegistry.sol."""
    fields = client.post("/qr/sign", json={"campaign_id": 1}).json()
    types = fields["typed_data"]["types"]["VisitSig"]
    encoded = ",".join(f"{f['type']} {f['name']}" for f in types)
    assert encoded == "uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash"


def test_payload_carries_the_campaign_geohash_as_bytes32():
    r = client.post("/qr/sign", json={"campaign_id": 1})
    message = r.json()["typed_data"]["message"]
    assert message["campaignId"] == 1
    # "dr5rsked" in ASCII, right-padded with zeros to 32 bytes.
    assert message["geohash"] == "0x" + b"dr5rsked".hex().ljust(64, "0")


def test_the_visitor_is_not_in_the_signature():
    """The merchant signs one QR for everyone, so it cannot name a visitor."""
    r = client.post("/qr/sign", json={"campaign_id": 1})
    assert "visitor" not in r.json()["typed_data"]["message"]


def test_every_call_gets_a_fresh_nonce():
    a = client.post("/qr/sign", json={"campaign_id": 1}).json()["nonce"]
    b = client.post("/qr/sign", json={"campaign_id": 1}).json()["nonce"]
    assert a != b


def test_signature_outlives_the_qr_on_screen():
    r = client.post("/qr/sign", json={"campaign_id": 1}).json()
    assert r["expiry"] > time.time() + 60
    assert r["rotate_after_seconds"] < r["expiry"] - time.time()


def test_unknown_campaign_returns_404():
    assert client.post("/qr/sign", json={"campaign_id": 999}).status_code == 404
