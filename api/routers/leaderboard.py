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
from api.schemas import LeaderboardEntry, PlayerStanding
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


# One player's own record, plus everyone standing above them. The Graph has no
# count aggregate, so a rank is the length of that second list. Capping it at a
# thousand keeps a single query bounded — past that the exact number stops
# meaning anything to the person reading it anyway.
ME = """
query Me($address: Bytes!) {
  visitor(id: $address) {
    id
    points
    visitCount
    distinctMerchants
  }
}
"""

ABOVE_ME = """
query AboveMe($points: Int!) {
  visitors(first: 1000, where: { points_gt: $points }) {
    id
  }
}
"""

JUST_ABOVE = """
query JustAbove($points: Int!) {
  visitors(first: 1, where: { points_gt: $points }, orderBy: points, orderDirection: asc) {
    points
  }
}
"""

RANK_CAP = 1000


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


def _standing_from_mock(address: str, zone: str | None, week: int | None):
    rows = MOCK_EXPLORERS if zone is None else [
        r for r in MOCK_EXPLORERS if r.zone == zone
    ]
    ordered = sorted(rows, key=lambda r: r.points or 0, reverse=True)

    mine = next((r for r in ordered if r.address.lower() == address.lower()), None)
    if mine is None:
        raise HTTPException(404, "That wallet has no verified visits yet")

    position = ordered.index(mine) + 1
    ahead = ordered[position - 2] if position > 1 else None

    return PlayerStanding(
        address=mine.address,
        label=mine.label,
        points=mine.points or 0,
        visits=mine.visits,
        distinct_merchants=mine.distinct_merchants or 0,
        rank=position,
        players=len(ordered),
        points_to_next=(ahead.points or 0) - (mine.points or 0) + 1 if ahead else None,
        zone=zone,
        zone_name=zone_name(zone) if zone else None,
        week_start=week_start_of(week) if week is not None else None,
    )


@router.get("/me", response_model=PlayerStanding)
def my_standing(
    address: str = Query(..., pattern=r"^0x[0-9a-fA-F]{40}$"),
    zone: str | None = Query(None, min_length=6, max_length=6, pattern="^[0-9b-hjkmnp-z]+$"),
    week: int | None = Query(None, ge=0),
):
    """Where one player stands, and how far the next place is."""
    config = get_config()
    if config.mock_mode:
        return _standing_from_mock(address, zone, week)

    try:
        node = subgraph.run(ME, {"address": address.lower()}).get("visitor")
        if node is None:
            raise HTTPException(404, "That wallet has no verified visits yet")

        points = int(node["points"])
        ahead = subgraph.run(ABOVE_ME, {"points": points}).get("visitors", [])
        nearest = subgraph.run(JUST_ABOVE, {"points": points}).get("visitors", [])
    except subgraph.SubgraphError as exc:
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc

    return PlayerStanding(
        address=node["id"],
        label=short(node["id"]),
        points=points,
        visits=int(node["visitCount"]),
        distinct_merchants=int(node["distinctMerchants"]),
        # Past a thousand places up, the exact number tells the reader nothing.
        rank=len(ahead) + 1 if len(ahead) < RANK_CAP else None,
        points_to_next=(int(nearest[0]["points"]) - points + 1) if nearest else None,
        zone=zone,
        zone_name=zone_name(zone) if zone else None,
        week_start=week_start_of(week) if week is not None else None,
    )


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
