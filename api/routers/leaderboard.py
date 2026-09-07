"""Two rankings, both counted by the chain rather than by us.

Ranked by visit count, which is what ships on the 13th. The points system —
ten a visit, a discovery bonus, the weekly reset, trivia — is written up as
the next step: it is a lot of arithmetic for something no prize asks for, and
a count already carries the argument that matters. Anyone can run these two
queries against the subgraph and get the same table we show.
"""

from fastapi import APIRouter, HTTPException, Query

from api import subgraph
from api.config import get_config
from api.mock_data import MOCK_EXPLORERS, MOCK_MERCHANTS
from api.schemas import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

EXPLORERS = """
query Explorers($first: Int!) {
  visitors(first: $first, orderBy: visitCount, orderDirection: desc) {
    id
    visitCount
    distinctMerchants
  }
}
"""

MERCHANTS = """
query Merchants($first: Int!) {
  merchants(first: $first, orderBy: visitCount, orderDirection: desc) {
    id
    visitCount
  }
}
"""

# Scoped to one zone, the ranking is counted from the visits themselves rather
# than from a stored total, because a wallet's lifetime count says nothing
# about how it did on these six blocks. A neighbourhood is small, so this stays
# cheap — and being first in it is something a person can actually manage,
# which a city-wide table never is.
ZONE_VISITS = """
query ZoneVisits($first: Int!, $zone: String!) {
  visits(first: $first, where: { zone: $zone }, orderBy: timestamp, orderDirection: desc) {
    visitor { id }
    merchant { id }
  }
}
"""


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


def _rank_within_zone(zone: str, scope: str, limit: int) -> list[LeaderboardEntry]:
    rows = subgraph.run(ZONE_VISITS, {"first": 1000, "zone": zone}).get("visits", [])

    key = "visitor" if scope == "explorers" else "merchant"
    counts: dict[str, int] = {}
    for row in rows:
        address = row[key]["id"]
        counts[address] = counts.get(address, 0) + 1

    ordered = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    return [
        LeaderboardEntry(rank=position, address=address, label=short(address), visits=n)
        for position, (address, n) in enumerate(ordered[:limit], start=1)
    ]


@router.get("", response_model=list[LeaderboardEntry])
def leaderboard(
    scope: str = Query("explorers", pattern="^(explorers|merchants)$"),
    limit: int = Query(20, ge=1, le=100),
    zone: str | None = Query(None, min_length=6, max_length=6, pattern="^[0-9b-hjkmnp-z]+$"),
):
    config = get_config()

    if config.mock_mode:
        rows = MOCK_EXPLORERS if scope == "explorers" else MOCK_MERCHANTS
        if zone is not None:
            rows = [r for r in rows if r.zone == zone]
        return rows[:limit]

    try:
        if zone is not None:
            return _rank_within_zone(zone, scope, limit)

        document = EXPLORERS if scope == "explorers" else MERCHANTS
        field = "visitors" if scope == "explorers" else "merchants"
        nodes = subgraph.run(document, {"first": limit}).get(field, [])
    except subgraph.SubgraphError as exc:
        # Never an empty table on failure — an empty leaderboard reads as "no
        # one has played yet", which is a very different thing from an outage.
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc

    return [
        LeaderboardEntry(
            rank=position,
            address=node["id"],
            label=short(node["id"]),
            visits=int(node["visitCount"]),
            distinct_merchants=(
                int(node["distinctMerchants"]) if "distinctMerchants" in node else None
            ),
        )
        for position, node in enumerate(nodes, start=1)
    ]
