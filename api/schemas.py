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
    # Null when the answer came from the vault rather than the subgraph: the
    # contract holds no creation time, only an index knows when something
    # happened. Left empty instead of guessed, so a caller can tell which of
    # the two answered.
    created_at: datetime | None = None


class SearchHit(BaseModel):
    campaign: Campaign
    distance_meters: int = Field(..., ge=0)


class QrSignRequest(BaseModel):
    campaign_id: int = Field(..., ge=0)


class LeaderboardEntry(BaseModel):
    rank: int = Field(..., ge=1)
    address: str
    "What to show when there is no name: a shortened address."
    label: str
    visits: int = Field(..., ge=0)
    """
    Only filled for explorers: how many different stores they have been to.
    It is the number the discovery bonus will reward, and it cannot be
    computed without an index of the chain.
    """
    distinct_merchants: int | None = None
    """
    Five a visit, ten at a store new to them, nothing twice in a day at the
    same one. Null on the merchant table: a merchant does not play, they are
    the board.
    """
    points: int | None = None
    "Six-character geohash prefix. Null on a city-wide table."
    zone: str | None = None
    "What to print for that zone: 'Lower East Side' rather than 'dr5rsk'."
    zone_name: str | None = None
    "Monday 00:00 UTC of the week shown. Null on the all-time table."
    week_start: int | None = None


class PlayerStanding(BaseModel):
    """One player's own view of the game.

    A bare position demotivates almost everyone: being 812th tells you nothing
    you want to hear. What moves people is their own progress and how close the
    next place is, so both travel with the rank.
    """

    address: str
    label: str
    points: int = Field(..., ge=0)
    visits: int = Field(..., ge=0)
    distinct_merchants: int = Field(..., ge=0)
    rank: int | None = Field(None, ge=1)
    "How many players this table holds, so a rank reads as '12 of 47'."
    players: int | None = Field(None, ge=0)
    "Points needed to pass whoever is directly above. Null when already first."
    points_to_next: int | None = Field(None, ge=1)
    zone: str | None = None
    zone_name: str | None = None
    week_start: int | None = None


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
    # What the contract actually stores: one human, not one wallet. It keys the
    # weekly 100/50/25/0 curve, so two visitors sharing a nullifier would share
    # a payout curve. Optional only while the samples stand in for the chain.
    nullifier_hash: str = Field("", pattern=r"^(0x[0-9a-fA-F]{64})?$")


class ClaimResponse(BaseModel):
    tx_hash: str
    status: str
    # False once the visitor has gas of their own and sends it themselves. The
    # relay is a convenience, never a requirement.
    relayed: bool = True


class EpochWindow(BaseModel):
    """Which batch of scores is open, and how long until it closes.

    The panel needs this to say "your score is final in 14 minutes" rather than
    leaving a held reward looking permanent.
    """

    epoch: int = Field(..., ge=0)
    start: int
    end: int
    seconds_remaining: int = Field(..., ge=0)


class EpochCommitment(BaseModel):
    """One closed epoch: the root, and enough to rebuild it independently."""

    epoch: int = Field(..., ge=0)
    "[start, end) in unix seconds — the visits this root was built from."
    start: int
    end: int
    root: str = Field(..., pattern=r"^0x[0-9a-fA-F]{64}$")
    "How many wallets are in the tree."
    wallets: int = Field(..., ge=1)
    # False until FraudOracle.commitEpoch exists and the contract is deployed.
    # Stated rather than assumed: a root we computed and a root anybody can
    # check against the chain are very different claims.
    committed: bool = False


class ScoreProof(BaseModel):
    """What we said about one wallet in one epoch, and the proof of it."""

    epoch: int = Field(..., ge=0)
    address: str
    "The model score, 0 to 1, for a person to read."
    score: float = Field(..., ge=0, le=1)
    "The same number as the contract takes it: basis points, 0 to 10_000."
    score_bps: int = Field(..., ge=0, le=10_000)
    root: str = Field(..., pattern=r"^0x[0-9a-fA-F]{64}$")
    """
    Siblings for `MerkleProof.verify`, bottom to top. Empty is valid and means
    the epoch held exactly one wallet, so the leaf is already the root.
    """
    proof: list[str]


class QrSignResponse(BaseModel):
    # The full EIP-712 document the merchant wallet signs. Handed over as-is so
    # the frontend passes it straight to the wallet without rebuilding it.
    typed_data: dict
    nonce: int
    expiry: int
    rotate_after_seconds: int
