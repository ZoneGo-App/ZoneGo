"""Reads a campaign straight from the contract, for what the index cannot answer.

The subgraph is where history lives, and every number a merchant can audit comes
from there. But an index only ever answers about the past: a campaign funded
thirty seconds ago is not in it yet, and `CampaignCreated` does not carry the
geohash or the radius at all, so the index cannot place a campaign in a zone.

One `eth_call` against the public `campaigns` mapping closes both gaps. What
comes back is the contract's own state, with nobody in between — not even our
own indexer.

This deliberately returns less than a `Campaign`: the getter has no creation
time, no visit count and no merchant name. Those live in the index or off chain,
and inventing them here would hide which of the two actually answered.
"""

import time
from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import Web3Exception

from api.config import get_config
from api.eip712 import geohash_from_bytes32
from api.geo import decode_geohash

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Only the one getter we call. Solidity writes this for a public mapping and
# flattens the struct into positional return values, so the order below is the
# order of the fields in `Campaign` in CampaignVault.sol — reordering them here
# silently swaps `dailyCap` for `radius` rather than failing.
CAMPAIGN_VAULT_ABI = [
    {
        "type": "function",
        "name": "campaigns",
        "stateMutability": "view",
        "inputs": [{"name": "campaignId", "type": "uint256"}],
        "outputs": [
            {"name": "merchant", "type": "address"},
            {"name": "rewardPerVisit", "type": "uint256"},
            {"name": "dailyCap", "type": "uint256"},
            {"name": "geohash", "type": "bytes32"},
            {"name": "radius", "type": "uint256"},
            {"name": "balance", "type": "uint256"},
        ],
    }
]


class ChainError(RuntimeError):
    pass


@dataclass(frozen=True)
class OnChainCampaign:
    """Exactly the six fields the contract holds, plus the decoded position."""

    campaign_id: int
    merchant: str
    reward_per_visit: int
    daily_cap: int
    geohash: str
    lat: float
    lon: float
    # `radius` in the contract. Named for its unit here so it cannot be read as
    # kilometres by anything that consumes it.
    radius_meters: int
    balance: int


_cache: dict[int, tuple[float, OnChainCampaign | None]] = {}


def clear_cache() -> None:
    _cache.clear()


def _vault():
    config = get_config()
    if not config.rpc_url:
        raise ChainError("RPC_URL is not set")
    if config.campaign_vault_address == ZERO_ADDRESS:
        raise ChainError("CAMPAIGN_VAULT_ADDRESS is not set")

    w3 = Web3(
        Web3.HTTPProvider(
            config.rpc_url,
            request_kwargs={"timeout": config.rpc_timeout_seconds},
        )
    )
    return w3.eth.contract(
        address=Web3.to_checksum_address(config.campaign_vault_address),
        abi=CAMPAIGN_VAULT_ABI,
    )


def get_campaign(campaign_id: int) -> OnChainCampaign | None:
    """The campaign as the contract holds it, or None if it was never created.

    A campaign that does not exist reads back as a zeroed struct rather than
    reverting, which is why the merchant address is the existence check — the
    same one the contract itself makes before funding.
    """
    config = get_config()
    hit = _cache.get(campaign_id)
    now = time.monotonic()
    if hit is not None and now - hit[0] < config.rpc_cache_seconds:
        return hit[1]

    try:
        merchant, reward, cap, geohash_raw, radius, balance = (
            _vault().functions.campaigns(campaign_id).call()
        )
    except Web3Exception as exc:
        raise ChainError(f"eth_call failed: {exc}") from exc

    campaign: OnChainCampaign | None = None
    if int(merchant, 16) != 0:
        geohash = geohash_from_bytes32(geohash_raw)
        lat, lon = decode_geohash(geohash)
        campaign = OnChainCampaign(
            campaign_id=campaign_id,
            merchant=merchant,
            reward_per_visit=reward,
            daily_cap=cap,
            geohash=geohash,
            lat=lat,
            lon=lon,
            radius_meters=radius,
            balance=balance,
        )

    # A miss is cached too. Asking a node for a campaign nobody created is a
    # round trip either way, and search will ask for the same one repeatedly.
    _cache[campaign_id] = (now, campaign)
    return campaign
