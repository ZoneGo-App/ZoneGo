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
from api.eip712 import geohash_from_bytes32
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

# What the chain already knows about one visitor: which human they proved to
# be, and when they last walked anywhere. Both come from `VisitRegistry` — the
# nullifier is written on their first claim and cannot move afterwards — so
# this asks the index to repeat a fact rather than to be trusted with one.
VISITOR_STANDING = """
query VisitorStanding($id: Bytes!) {
  visitor(id: $id) {
    id
    nullifierHash
    visits(first: 1, orderBy: timestamp, orderDirection: desc) {
      timestamp
    }
  }
}
"""

# Everyone who was seen inside one epoch. Ordered by timestamp so the page we
# take is the earliest slice of the window rather than an arbitrary one — an
# epoch has to be rebuildable to the same root by anyone who asks.
VISITORS_BETWEEN = """
query VisitorsBetween($start: BigInt!, $end: BigInt!, $first: Int!, $skip: Int!) {
  visits(
    where: { timestamp_gte: $start, timestamp_lt: $end }
    orderBy: timestamp
    orderDirection: asc
    first: $first
    skip: $skip
  ) {
    visitor { id }
  }
}
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
    # InvalidURL is not an HTTPError — it is a plain Exception — so listing it
    # separately is the difference between a 502 that names a bad SUBGRAPH_URL
    # and a 500 that names nothing.
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise SubgraphError(f"subgraph request failed: {exc}") from exc

    # GraphQL answers 200 with an errors array, so a failed query looks like a
    # success to anything that only checks the status code.
    if body.get("errors"):
        raise SubgraphError(str(body["errors"][0].get("message", body["errors"])))

    data = body.get("data") or {}
    _cache[key] = (now, data)
    return data


def to_campaign(node: dict[str, Any]) -> Campaign:
    geohash = geohash_from_bytes32(node["geohash"])
    lat, lon = decode_geohash(geohash)
    merchant = node["merchant"]["id"]
    balance = int(node["balance"])
    reward = int(node["rewardPerVisit"])

    return Campaign(
        campaign_id=int(node["campaignId"]),
        merchant=merchant,
        # Off-chain metadata does not exist yet, so the address stands in. A
        # placeholder is better than an empty string, which the model rejects.
        merchant_name=f"Merchant {merchant[:6]}…{merchant[-4:]}",
        category="",
        sells="",
        reward_per_visit=reward,
        daily_cap=int(node["dailyCap"]) or 1,
        lat=lat,
        lon=lon,
        geohash=geohash,
        radius_meters=int(node["radiusMeters"]) or 1,
        balance=balance,
        # The index's own flag says only that the merchant has not switched the
        # campaign off. It says nothing about whether there is money left, and a
        # campaign created but never funded comes back from it as active with a
        # balance of zero — which is what search then puts on the map.
        #
        # Sending somebody on a fifteen-minute walk to a store that cannot pay
        # them is the one failure this product cannot afford, so `active` here
        # means what a visitor needs it to mean: switched on *and* able to cover
        # one more visit.
        active=bool(node["active"]) and balance >= reward,
        created_at=int(node["createdAt"]),
    )


def list_campaigns(first: int = 100) -> list[Campaign]:
    data = run(LIST_CAMPAIGNS, {"first": first})
    return [to_campaign(node) for node in data.get("campaigns", [])]


def visitor_standing(visitor: str) -> tuple[str, int] | None:
    """The nullifier this wallet is bound to, and when it last claimed.

    Returns None when the chain has never seen them prove anything — no
    visitor, or a visitor with no nullifier yet — which is the case that has to
    go through Selfie Check rather than around it.

    The timestamp is the last visit rather than the moment they verified,
    because we keep no record of the second and the chain keeps the first.
    Today every claim carries a fresh attestation, so the two are the same
    instant; if that ever stops being true this reads older than reality, which
    is the safe direction — it asks for a selfie sooner, never later.
    """
    node = run(VISITOR_STANDING, {"id": visitor.lower()}).get("visitor")
    if not node:
        return None

    nullifier = node.get("nullifierHash")
    visits = node.get("visits") or []
    if not nullifier or not visits:
        return None

    return nullifier, int(visits[0]["timestamp"])


def get_campaign(campaign_id: int) -> Campaign | None:
    # Entity ids are the campaign id as bytes, the same key the mappings write.
    key = "0x" + format(campaign_id, "x").rjust(2, "0")
    if len(key) % 2:
        key = "0x0" + key[2:]
    node = run(GET_CAMPAIGN, {"id": key}).get("campaign")
    return to_campaign(node) if node else None


# The Graph caps a page at 1000 rows whatever we ask for.
PAGE = 1000


def visitors_between(start: int, end: int) -> list[str]:
    """Distinct wallets with a visit in [start, end), lowercased and sorted.

    Paged to the end rather than capped: an epoch that silently dropped its
    thousandth visitor would commit a root that leaves that person unable to
    prove their own score, which is the one thing this must never do.
    """
    seen: set[str] = set()
    skip = 0
    while True:
        rows = run(
            VISITORS_BETWEEN,
            {"start": str(start), "end": str(end), "first": PAGE, "skip": skip},
        ).get("visits", [])
        for row in rows:
            seen.add(row["visitor"]["id"].lower())
        if len(rows) < PAGE:
            return sorted(seen)
        skip += PAGE
