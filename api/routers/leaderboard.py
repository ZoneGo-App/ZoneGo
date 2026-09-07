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


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


@router.get("", response_model=list[LeaderboardEntry])
def leaderboard(
    scope: str = Query("explorers", pattern="^(explorers|merchants)$"),
    limit: int = Query(20, ge=1, le=100),
):
    config = get_config()

    if config.mock_mode:
        rows = MOCK_EXPLORERS if scope == "explorers" else MOCK_MERCHANTS
        return rows[:limit]

    document = EXPLORERS if scope == "explorers" else MERCHANTS
    field = "visitors" if scope == "explorers" else "merchants"
    try:
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
