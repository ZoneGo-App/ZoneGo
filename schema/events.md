# Event schema — FROZEN

Agreed Sept 5. Not changed without all four of us agreeing.
Last window for changes: Monday Sept 7. After that, gaps are solved in the
subgraph mapping or the API — never by redeploying the contract.

Any field added after Sept 7 must be **nullable**, so the subgraph can be
grafted onto the previous one without reindexing.

## Design decision

`VisitRecorded` and `RewardPaid` are **separate events**, not one event
carrying the amount.

Between them lives the `held` state: visit confirmed, payout frozen because
the fraud score crossed the threshold. Without that gap the fraud model
decides nothing — by the time it scores, the money is already gone.

## CampaignCreated
- campaignId
- merchant
- rewardPerVisit
- dailyCap
- geohash
- radiusMeters
- timestamp

## CampaignFunded
- campaignId
- merchant
- amount
- timestamp

## VisitRecorded
- campaignId
- visitor
- nullifierHash
- sigHash
- timestamp

## RewardPaid
- campaignId
- visitor
- amount
- timestamp

## EpochCommitted
- epoch
- merkleRoot
- timestamp

## Open with Sebastián
- Exact type of each field
- Which ones are `indexed`
- Whether geohash is `bytes12` or `string`
- Amounts in USDC minor units (6 decimals) — assumed yes
