from fastapi import APIRouter, HTTPException

from api import chain, subgraph
from api.config import get_config
from api.mock_data import CAMPAIGNS
from api.schemas import Campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _from_chain(onchain: chain.OnChainCampaign) -> Campaign:
    """What the vault holds, shaped like a Campaign.

    Three fields the contract does not have: the merchant's name and what they
    stock are off-chain metadata, and the creation time is something only an
    index knows. They come back empty rather than invented.
    """
    return Campaign(
        campaign_id=onchain.campaign_id,
        merchant=onchain.merchant,
        merchant_name=f"Merchant {onchain.merchant[:6]}…{onchain.merchant[-4:]}",
        category="",
        sells="",
        reward_per_visit=onchain.reward_per_visit,
        daily_cap=onchain.daily_cap or 1,
        lat=onchain.lat,
        lon=onchain.lon,
        geohash=onchain.geohash,
        radius_meters=onchain.radius_meters or 1,
        balance=onchain.balance,
        # A campaign with nothing left in it cannot pay for a visit, and the
        # contract has no flag of its own to read instead.
        active=onchain.balance > 0,
    )


def _with_live_state(campaign: Campaign) -> Campaign:
    """The index answers about the past, the vault about right now.

    Two reasons to ask both. The balance moves with every reward paid, so an
    index a block behind shows a merchant money they have already spent. And
    `CampaignCreated` does not carry the geohash or the radius yet, so until it
    does the index cannot place a campaign at all — an empty geohash decodes to
    (0, 0), a valid point in the Gulf of Guinea and eight thousand kilometres
    from Delancey Street.
    """
    try:
        onchain = chain.get_campaign(campaign.campaign_id)
    except chain.ChainError:
        # The index already answered. A node we cannot reach makes that answer
        # staler, not wrong, so it is not worth failing the request over.
        return campaign

    if onchain is None:
        return campaign

    return campaign.model_copy(
        update={
            "geohash": onchain.geohash,
            "lat": onchain.lat,
            "lon": onchain.lon,
            "radius_meters": onchain.radius_meters or campaign.radius_meters,
            "balance": onchain.balance,
        }
    )


@router.get("", response_model=list[Campaign])
def list_campaigns():
    config = get_config()
    if config.mock_mode:
        return CAMPAIGNS
    try:
        # No node overlay here: it would be one eth_call per campaign, on the
        # route search hits hardest. The single-campaign route below is where a
        # round trip to the chain earns itself.
        return subgraph.list_campaigns()
    except subgraph.SubgraphError as exc:
        # 502, not 500: the failure is upstream, and a caller retrying makes
        # sense. Studio rate limits and reindexing both land here.
        raise HTTPException(502, f"Subgraph unavailable: {exc}") from exc


def resolve(campaign_id: int) -> Campaign:
    """One campaign as both sources see it, or an HTTP error saying why not.

    Not folded into the route below because the relay validates a claim against
    this same view. Two copies of "which source answers" would drift, and the
    drift would show up as a claim we refuse for a campaign the caller can read
    perfectly well.
    """
    config = get_config()
    if config.mock_mode:
        for c in CAMPAIGNS:
            if c.campaign_id == campaign_id:
                return c
        raise HTTPException(404, "Campaign not found")

    campaign = None
    subgraph_error: subgraph.SubgraphError | None = None
    try:
        campaign = subgraph.get_campaign(campaign_id)
    except subgraph.SubgraphError as exc:
        subgraph_error = exc

    if campaign is not None:
        return _with_live_state(campaign)

    # Nothing in the index: either it has not caught up, or it is down. The
    # vault answers in both cases — a campaign exists on chain a block before
    # it exists anywhere else.
    try:
        onchain = chain.get_campaign(campaign_id)
    except chain.ChainError as exc:
        if subgraph_error is not None:
            raise HTTPException(502, f"Subgraph unavailable: {subgraph_error}") from subgraph_error
        raise HTTPException(502, f"Node unavailable: {exc}") from exc

    if onchain is None:
        raise HTTPException(404, "Campaign not found")
    return _from_chain(onchain)


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: int):
    return resolve(campaign_id)
