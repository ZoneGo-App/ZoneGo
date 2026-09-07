"""Reads campaign and visit history from the subgraph, never from our own store.

This is the point of using The Graph here: a merchant can run the same query we
run and get the same answer, so none of these numbers require trusting us.

What the chain does not carry is the merchant's name and the text describing
what they stock. Those are off-chain metadata; until there is somewhere to keep
them, a campaign read back from the chain gets a placeholder name.
"""

import time
from typing import Any

import httpx

from api.config import get_config
from api.geo import decode_geohash
from api.schemas import Campaign


class SubgraphError(RuntimeError):
    pass


CAMPAIGN_FIELDS = """
  id
  campaignId
  merchant { id }
  rewardPerVisit
  dailyCap
  geohash
  radiusMeters
  balance
  active
  createdAt
  visitCount
  totalPaid
"""

LIST_CAMPAIGNS = f"""
query Campaigns($first: Int!) {{
  campaigns(first: $first, where: {{ active: true }}, orderBy: createdAt, orderDirection: desc) {{
    {CAMPAIGN_FIELDS}
  }}
}}
"""

GET_CAMPAIGN = f"""
query Campaign($id: Bytes!) {{
  campaign(id: $id) {{
    {CAMPAIGN_FIELDS}
  }}
}}
"""

# Query result cache. A merchant panel and a search page hit the same campaign
# list within the same second; a few seconds of staleness is invisible to a
# person walking down a street, and it keeps us inside the Studio rate limit.
_cache: dict[str, tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


def run(document: str, variables: dict[str, Any]) -> dict[str, Any]:
    config = get_config()
    if not config.subgraph_url:
        raise SubgraphError("SUBGRAPH_URL is not set")

    key = f"{document}:{sorted(variables.items())}"
    hit = _cache.get(key)
    now = time.monotonic()
    if hit is not None and now - hit[0] < config.subgraph_cache_seconds:
        return hit[1]

    try:
        response = httpx.post(
            config.subgraph_url,
            json={"query": document, "variables": variables},
            timeout=config.subgraph_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as exc:
        raise SubgraphError(f"subgraph request failed: {exc}") from exc

    # GraphQL answers 200 with an errors array, so a failed query looks like a
    # success to anything that only checks the status code.
    if body.get("errors"):
        raise SubgraphError(str(body["errors"][0].get("message", body["errors"])))

    data = body.get("data") or {}
    _cache[key] = (now, data)
    return data


def _geohash_text(raw: str) -> str:
    """The chain holds bytes32; strip the 0x and the zero padding."""
    return bytes.fromhex(raw.removeprefix("0x")).rstrip(b"\x00").decode("ascii")


def to_campaign(node: dict[str, Any]) -> Campaign:
    geohash = _geohash_text(node["geohash"])
    lat, lon = decode_geohash(geohash)
    merchant = node["merchant"]["id"]

    return Campaign(
        campaign_id=int(node["campaignId"]),
        merchant=merchant,
        # Off-chain metadata does not exist yet, so the address stands in. A
        # placeholder is better than an empty string, which the model rejects.
        merchant_name=f"Merchant {merchant[:6]}…{merchant[-4:]}",
        category="",
        sells="",
        reward_per_visit=int(node["rewardPerVisit"]),
        daily_cap=int(node["dailyCap"]) or 1,
        lat=lat,
        lon=lon,
        geohash=geohash,
        radius_meters=int(node["radiusMeters"]) or 1,
        balance=int(node["balance"]),
        active=bool(node["active"]),
        created_at=int(node["createdAt"]),
    )


def list_campaigns(first: int = 100) -> list[Campaign]:
    data = run(LIST_CAMPAIGNS, {"first": first})
    return [to_campaign(node) for node in data.get("campaigns", [])]


def get_campaign(campaign_id: int) -> Campaign | None:
    # Entity ids are the campaign id as bytes, the same key the mappings write.
    key = "0x" + format(campaign_id, "x").rjust(2, "0")
    if len(key) % 2:
        key = "0x0" + key[2:]
    node = run(GET_CAMPAIGN, {"id": key}).get("campaign")
    return to_campaign(node) if node else None
