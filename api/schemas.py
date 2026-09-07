from datetime import datetime

from pydantic import BaseModel, Field


class Campaign(BaseModel):
    campaign_id: int = Field(..., ge=0)
    merchant: str
    merchant_name: str = Field(..., min_length=1, max_length=120)
    category: str
    # Free text the merchant writes about what they stock. This is what search
    # matches on — a bodega that sells sneakers is invisible to Google, which
    # only knows the category the owner picked from a list.
    sells: str = Field("", max_length=400)
    reward_per_visit: int = Field(..., gt=0)
    daily_cap: int = Field(..., gt=0)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    geohash: str
    radius_meters: int = Field(..., gt=0, le=2000)
    balance: int = Field(..., ge=0)
    active: bool = True
    created_at: datetime


class SearchHit(BaseModel):
    campaign: Campaign
    distance_meters: int = Field(..., ge=0)
