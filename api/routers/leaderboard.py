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
from api.points import week_start_of
from api.schemas import LeaderboardEntry
from api.zones import zone_name

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

# Explorers rank by points, merchants by visits received. A merchant does not
# play the game — they are the board.
EXPLORERS = """
query Explorers($first: Int!) {
  visitors(first: $first, orderBy: points, orderDirection: desc) {
    id
    points
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

EXPLORERS_WEEK = """
query ExplorersWeek($first: Int!, $weekStart: BigInt!) {
  visitorWeeks(
    first: $first
    where: { weekStart: $weekStart }
    orderBy: points
    orderDirection: desc
  ) {
    visitor { id }
    points
    visits
    newMerchants
  }
}
"""

MERCHANTS_WEEK = """
query MerchantsWeek($first: Int!, $weekStart: BigInt!) {
  merchantWeeks(
    first: $first
    where: { weekStart: $weekStart }
    orderBy: visits
    orderDirection: desc
  ) {
    merchant { id }
    visits
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
    points
  }
}
"""


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


def _rank_within_zone(zone: str, scope: str, limit: int) -> list[LeaderboardEntry]:
    rows = subgraph.run(ZONE_VISITS, {"first": 1000, "zone": zone}).get("visits", [])

    key = "visitor" if scope == "explorers" else "merchant"
    visits: dict[str, int] = {}
    points: dict[str, int] = {}
    for row in rows:
        address = row[key]["id"]
        visits[address] = visits.get(address, 0) + 1
        points[address] = points.get(address, 0) + int(row.get("points", 0))

    # Explorers compete on points inside a zone; merchants on visits received.
    ordering = points if scope == "explorers" else visits
    ordered = sorted(ordering.items(), key=lambda pair: pair[1], reverse=True)

    return [
        LeaderboardEntry(
            rank=position,
            address=address,
            label=short(address),
            visits=visits[address],
            points=points[address] if scope == "explorers" else None,
            zone=zone,
            zone_name=zone_name(zone),
        )
        for position, (address, _) in enumerate(ordered[:limit], start=1)
    ]


def _rank_for_week(scope: str, week_start: int, limit: int) -> list[LeaderboardEntry]:
    document = EXPLORERS_WEEK if scope == "explorers" else MERCHANTS_WEEK
    field = "visitorWeeks" if scope == "explorers" else "merchantWeeks"
    nodes = subgraph.run(document, {"first": limit, "weekStart": str(week_start)}).get(
        field, []
    )

    owner = "visitor" if scope == "explorers" else "merchant"
    return [
        LeaderboardEntry(
            rank=position,
            address=node[owner]["id"],
            label=short(node[owner]["id"]),
            visits=int(node["visits"]),
            points=int(node["points"]) if scope == "explorers" else None,
            distinct_merchants=(
                int(node["newMerchants"]) if scope == "explorers" else None
            ),
            week_start=week_start,
        )
        for position, node in enumerate(nodes, start=1)
    ]


@router.get("", response_model=list[LeaderboardEntry])
def leaderboard(
    scope: str = Query("explorers", pattern="^(explorers|merchants)$"),
    limit: int = Query(20, ge=1, le=100),
    zone: str | None = Query(None, min_length=6, max_length=6, pattern="^[0-9b-hjkmnp-z]+$"),
    week: int | None = Query(
        None,
        ge=0,
        description=(
            "Any unix timestamp inside the week you want; it is snapped to that "
            "Monday. Leave it out for the all-time table."
        ),
    ),
):
    config = get_config()

    if config.mock_mode:
        rows = MOCK_EXPLORERS if scope == "explorers" else MOCK_MERCHANTS
        if zone is not None:
            rows = [r for r in rows if r.zone == zone]
        if week is not None:
            start = week_start_of(week)
            rows = [r.model_copy(update={"week_start": start}) for r in rows]
        return rows[:limit]

    try:
        if zone is not None:
            return _rank_within_zone(zone, scope, limit)
        if week is not None:
            return _rank_for_week(scope, week_start_of(week), limit)

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
            points=int(node["points"]) if "points" in node else None,
            distinct_merchants=(
                int(node["distinctMerchants"]) if "distinctMerchants" in node else None
            ),
        )
        for position, node in enumerate(nodes, start=1)
    ]
