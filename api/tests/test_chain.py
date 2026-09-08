"""The node client, exercised against a canned `eth_call` answer.

No network here. What matters is that the ABI fragment decodes the struct in
the order CampaignVault.sol declares it — get that wrong and a campaign comes
back with its daily cap in the radius field, quietly, with no error anywhere.
"""

import pytest
from web3 import Web3

from api import chain
from api.config import get_config

VAULT = "0x01422196A7768839f24E465115Ff97E170186Bf1"
MERCHANT = "0x1f6bfd8f9242ac5eef6b21082a9c460907e39e03"


def struct(
    *,
    merchant: str = MERCHANT,
    reward: int = 50_000,
    cap: int = 60,
    geohash: str = "dr5rsked",
    radius: int = 120,
    balance: int = 48_500_000,
) -> str:
    """Six 32-byte words, the way a node returns a flattened struct."""
    return "0x" + "".join(
        [
            merchant.removeprefix("0x").rjust(64, "0"),
            format(reward, "064x"),
            format(cap, "064x"),
            geohash.encode("ascii").hex().ljust(64, "0"),
            format(radius, "064x"),
            format(balance, "064x"),
        ]
    )


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "rpc_url", "https://example.test/rpc")
    monkeypatch.setattr(config, "campaign_vault_address", VAULT)
    chain.clear_cache()
    yield
    chain.clear_cache()


def answer(monkeypatch, result):
    calls = {"n": 0}

    def fake(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": hex(84532)}
        calls["n"] += 1
        if isinstance(result, dict):
            return {"jsonrpc": "2.0", "id": 1, **result}
        return {"jsonrpc": "2.0", "id": 1, "result": result}

    monkeypatch.setattr(Web3.HTTPProvider, "make_request", fake)
    return calls


def test_the_struct_decodes_field_for_field(monkeypatch):
    answer(monkeypatch, struct())
    campaign = chain.get_campaign(1)
    assert campaign.campaign_id == 1
    assert campaign.merchant.lower() == MERCHANT
    assert campaign.reward_per_visit == 50_000
    assert campaign.daily_cap == 60
    assert campaign.radius_meters == 120
    assert campaign.balance == 48_500_000


def test_the_cap_and_the_radius_do_not_swap(monkeypatch):
    """Both are uint256 and adjacent, so only distinct values catch a reorder."""
    answer(monkeypatch, struct(cap=7, radius=999))
    campaign = chain.get_campaign(1)
    assert campaign.daily_cap == 7
    assert campaign.radius_meters == 999


def test_the_geohash_comes_back_as_coordinates(monkeypatch):
    answer(monkeypatch, struct())
    campaign = chain.get_campaign(1)
    assert campaign.geohash == "dr5rsked"
    assert 40.71 < campaign.lat < 40.73
    assert -73.99 < campaign.lon < -73.98


def test_a_campaign_nobody_created_is_none(monkeypatch):
    """A missing key reads back zeroed rather than reverting."""
    answer(monkeypatch, struct(merchant=chain.ZERO_ADDRESS, reward=0, cap=0, balance=0))
    assert chain.get_campaign(999) is None


def test_repeated_reads_hit_the_cache(monkeypatch):
    calls = answer(monkeypatch, struct())
    chain.get_campaign(1)
    chain.get_campaign(1)
    assert calls["n"] == 1


def test_a_missing_campaign_is_cached_too(monkeypatch):
    calls = answer(monkeypatch, struct(merchant=chain.ZERO_ADDRESS, reward=0, cap=0, balance=0))
    chain.get_campaign(999)
    chain.get_campaign(999)
    assert calls["n"] == 1


def test_a_missing_rpc_url_fails_loudly(monkeypatch):
    monkeypatch.setattr(get_config(), "rpc_url", "")
    with pytest.raises(chain.ChainError):
        chain.get_campaign(1)


def test_a_missing_vault_address_fails_loudly(monkeypatch):
    monkeypatch.setattr(get_config(), "campaign_vault_address", chain.ZERO_ADDRESS)
    with pytest.raises(chain.ChainError):
        chain.get_campaign(1)


def test_an_rpc_error_is_not_an_empty_campaign(monkeypatch):
    """A node that answers with an error must not read as 'no such campaign'."""
    answer(monkeypatch, {"error": {"code": -32000, "message": "execution reverted"}})
    with pytest.raises(chain.ChainError):
        chain.get_campaign(1)
