from datetime import datetime

from pydantic import BaseModel, Field


class Campaign(BaseModel):
    campaign_id: int = Field(..., ge=0)
    merchant: str
    merchant_name: str = Field(..., min_length=1, max_length=120)
    category: str
    reward_per_visit: int = Field(..., gt=0)
    daily_cap: int = Field(..., gt=0)
    geohash: str
    radius_meters: int = Field(..., gt=0, le=2000)
    balance: int = Field(..., ge=0)
    active: bool = True
    created_at: datetime
