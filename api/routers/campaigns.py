from fastapi import APIRouter, HTTPException

from api import subgraph
from api.config import get_config
from api.mock_data import CAMPAIGNS
from api.schemas import Campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[Campaign])
def list_campaigns():
    config = get_config()
    if config.mock_mode:
        return CAMPAIGNS
    try:
        return subgraph.list_campaigns()
    except subgraph.SubgraphError as exc:
        # 502, not 500: the failure is upstream, and a caller retrying makes
        # sense. Studio rate limits and reindexing both land here.
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: int):
    config = get_config()
    if config.mock_mode:
        for c in CAMPAIGNS:
            if c.campaign_id == campaign_id:
                return c
        raise HTTPException(404, "Campaign not found")

    try:
        campaign = subgraph.get_campaign(campaign_id)
    except subgraph.SubgraphError as exc:
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc

    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    return campaign
