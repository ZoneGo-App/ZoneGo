"""Fraud scoring, and the decision it drives.

The score is not a figure on a dashboard: it decides whether a reward is
released or frozen. That gap between VisitRecorded and RewardPaid is the whole
reason the two are separate events — score after the money is gone and the
model decides nothing.

Edmer owns the model. This endpoint owns the decision: comparing the score to
the threshold, and always returning the three features that carried it.
"""

import hashlib

from fastapi import APIRouter, HTTPException

from api.config import get_config
from api.schemas import FeatureWeight, ScoreRequest, ScoreResponse

router = APIRouter(prefix="/score", tags=["score"])

# The day-2 feature set. Names are fixed here so the frontend can label them
# before the trained model exists.
FEATURE_NAMES = (
    "seconds_since_previous_claim",
    "implied_speed_between_stores",
    "deviation_from_store_modal_hour",
    "co_visitation_degree",
)


def _placeholder_score(visitor: str, campaign_id: int) -> tuple[float, list[FeatureWeight]]:
    """Stable stand-in until the model is served.

    Derived from the address so the same wallet always scores the same. That
    makes the frontend testable and lets the demo seed a wallet that gets held.
    """
    digest = hashlib.sha256(f"{visitor.lower()}:{campaign_id}".encode()).digest()
    score = digest[0] / 255

    features = [
        FeatureWeight(
            name=name,
            value=round(digest[i + 1] / 255, 4),
            weight=round(digest[i + 5] / 255, 4),
        )
        for i, name in enumerate(FEATURE_NAMES)
    ]
    features.sort(key=lambda f: f.weight, reverse=True)
    return round(score, 4), features[:3]


def wallet_score(visitor: str) -> float:
    """One score for a wallet, independent of any single visit.

    What an epoch commits is a wallet and a number, so the per-claim score is
    the wrong shape for it. Edmer's model replaces the derivation, not this
    signature.
    """
    value, _ = _placeholder_score(visitor, 0)
    return value


@router.post("", response_model=ScoreResponse)
def score(req: ScoreRequest):
    config = get_config()
    if not config.mock_mode:
        raise HTTPException(501, "Fraud model not served yet")

    value, features = _placeholder_score(req.visitor, req.campaign_id)

    return ScoreResponse(
        visitor=req.visitor,
        score=value,
        threshold=config.fraud_threshold,
        decision="hold" if value >= config.fraud_threshold else "pay",
        top_features=features,
    )
