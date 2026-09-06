from fastapi import APIRouter, HTTPException

from api.config import get_config
from api.mock_data import CAMPAIGNS
from api.schemas import Campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[Campaign])
def list_campaigns():
    config = get_config()
    if config.mock_mode:
        return CAMPAIGNS
    raise HTTPException(501, "Subgraph not connected yet")


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: int):
    config = get_config()
    if config.mock_mode:
        for c in CAMPAIGNS:
            if c.campaign_id == campaign_id:
                return c
        raise HTTPException(404, "Campaign not found")
    raise HTTPException(501, "Subgraph not connected yet")
