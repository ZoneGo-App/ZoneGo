"""Search is the front door of the product: what someone opens the app to do.

Plain text matching, no model. The merchant types "sneakers" and the visitor
searches "sneakers". Category and stock text are matched the same way, so a
bodega that stocks sneakers shows up for that word even though its category
says corner store.
"""

from fastapi import APIRouter, Query

from api.config import get_config
from api.geo import distance_meters
from api.mock_data import CAMPAIGNS
from api.schemas import SearchHit

router = APIRouter(prefix="/search", tags=["search"])

# What the visitor picks in the UI. Anything else is rejected, so the API and
# the radius selector can never disagree.
ALLOWED_RADIUS_KM = (1, 5, 10)


def _matches(campaign, needle: str) -> bool:
    if not needle:
        return True
    haystack = f"{campaign.merchant_name} {campaign.category} {campaign.sells}".lower()
    # Every word has to appear somewhere: "running sneakers" should not match a
    # store that only sells laces.
    return all(word in haystack for word in needle.lower().split())


@router.get("", response_model=list[SearchHit])
def search(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    q: str = Query("", max_length=120),
    radius_km: int = Query(1),
):
    if radius_km not in ALLOWED_RADIUS_KM:
        radius_km = ALLOWED_RADIUS_KM[0]

    config = get_config()
    source = CAMPAIGNS if config.mock_mode else []

    hits = []
    for campaign in source:
        if not campaign.active or not _matches(campaign, q):
            continue
        metres = distance_meters(lat, lon, campaign.lat, campaign.lon)
        if metres > radius_km * 1000:
            continue
        hits.append(SearchHit(campaign=campaign, distance_meters=round(metres)))

    # Nearest first. Someone standing on Delancey wants the block they are on,
    # not the best paying store fifteen minutes away.
    hits.sort(key=lambda h: h.distance_meters)
    return hits
