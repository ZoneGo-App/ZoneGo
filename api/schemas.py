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


class QrSignRequest(BaseModel):
    campaign_id: int = Field(..., ge=0)


class ScoreRequest(BaseModel):
    visitor: str = Field(..., pattern=r"^0x[0-9a-fA-F]{40}$")
    campaign_id: int = Field(..., ge=0)


class FeatureWeight(BaseModel):
    name: str
    value: float
    # How much this feature pushed the score up. The Graph asks for the
    # reasoning, not just the raw result, so we always hand back the three that
    # mattered most rather than a lone number.
    weight: float


class ScoreResponse(BaseModel):
    visitor: str
    score: float = Field(..., ge=0, le=1)
    threshold: float
    # "pay" releases the reward, "hold" freezes it between VisitRecorded and
    # RewardPaid. A hold is reversible: the visitor can appeal.
    decision: str
    top_features: list[FeatureWeight]


class ClaimRequest(BaseModel):
    """Everything the visitor's phone read off the QR, plus who they are.

    The merchant signature travels untouched from the QR to the contract. The
    relay only pays the gas — it cannot alter any of this without the contract
    rejecting the signature.
    """

    campaign_id: int = Field(..., ge=0)
    nonce: int = Field(..., ge=0)
    expiry: int = Field(..., gt=0)
    geohash: str = Field(..., pattern=r"^0x[0-9a-fA-F]{64}$")
    signature: str = Field(..., pattern=r"^0x[0-9a-fA-F]{130}$")
    visitor: str = Field(..., pattern=r"^0x[0-9a-fA-F]{40}$")
    world_proof: str = Field("", max_length=4096)


class ClaimResponse(BaseModel):
    tx_hash: str
    status: str
    # False once the visitor has gas of their own and sends it themselves. The
    # relay is a convenience, never a requirement.
    relayed: bool = True


class QrSignResponse(BaseModel):
    # The full EIP-712 document the merchant wallet signs. Handed over as-is so
    # the frontend passes it straight to the wallet without rebuilding it.
    typed_data: dict
    nonce: int
    expiry: int
    rotate_after_seconds: int
