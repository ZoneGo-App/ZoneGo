# Feedback for The Graph

## What we integrated

A subgraph on base-sepolia indexing three contracts — `CampaignVault`,
`VisitRegistry` and `FraudOracle` — into ten entities. Deployed to Subgraph
Studio as `zone-go`, currently v0.0.2, republished from block 46725201 when the
contracts were redeployed.

graph-cli 0.97.1, graph-ts 0.38.1, specVersion 1.0.0.

The API reads campaigns, search, both leaderboards and the per-epoch visitor set
from it. Nothing the product shows comes from a database of our own.

## What worked well

Scoring inside the mappings instead of in our server. Points, distinct-merchant
counts and weekly buckets are written as events arrive, so a player can rerun
our queries and check their own score against the chain rather than trusting us.
That property is the reason the leaderboard is worth showing at all, and we
could not have had it with an indexer we ran ourselves.

`@derivedFrom` and an entity per visitor-merchant pair turned the discovery
bonus — ten points the first time at each store, five after that — into a lookup
instead of a scan.

## What took longer than it should have

**Event-only ABIs.** The ABI a subgraph needs carries events and nothing else,
which is correct for indexing. But the moment our API had to read
`campaigns(campaignId)` from the node for a live balance, that file was useless
— two entries, both events — and we hand-wrote the function fragment. Nothing
warns that the ABI you assemble for the subgraph is not the ABI the rest of your
stack will need.

**Seven "Skip migration" lines on every deploy.** apiVersion 0.0.1→0.0.6 and
specVersion 0.0.1→0.0.4 print on a manifest that already declares 1.0.0. Every
run looks like something is being repaired.

## Documentation

### Issues we found

| Date | What we did | What we expected | What happened |
|---|---|---|---|
| Sept 7 | Wrote a `"…"` field description wrapped onto a second line in `schema.graphql` | The schema to build | Rejected. A description that wraps has to be a `"""…"""` block, and every example in the schema docs is single-line, so there was nothing to read that showed the difference |

### What was missing

A page on reading contract state from an application that already has a
subgraph. The split we ended up with — the index for history, the node for the
balance right now — is the normal case for anything showing live funds, and
every example we found does one or the other, never both. We worked it out by
building it twice.

## Support

No one from The Graph team answered a single question in the
`partner-the-graph` Discord channel between Sept 3 and Sept 5. Five questions
went unanswered, including a Subgraph Studio email verification failure
reported by another participant.

**`skip` stops at 5,000, and the error says so only when you get there.** Our
fraud pipeline first paginated visits with `first: 1000, skip: page * 1000`.
Against our own deployed subgraph, `skip: 5000` answers and `skip: 5001` returns
`"The skip argument must be between 0 and 5000"`. So the loader could read 6,000
visits at most, and the 6,001st broke scoring for everyone. We moved to a cursor
on `(timestamp, id)` with an `or:` filter, which has no ceiling and doubles as
the incremental refresh. The limit is documented, but nothing in Studio or the
CLI surfaces it while a subgraph is small, which is exactly when a pagination
strategy gets chosen.

**Indexing the money in and not the money out.** The first manifest handled
`CampaignCreated` and `CampaignFunded` only. The vault also emits
`CampaignWithdrawn`, `CampaignPaused` and `CampaignUnpaused`, and without
handlers the index kept a withdrawn campaign's balance and a paused campaign's
`active` flag forever. `graph codegen` built cleanly with the events missing
from the ABI; a warning for events a contract emits that no handler covers
would have caught it.

## Why The Graph was necessary, not decorative

The graph features our fraud model relies on — co-visitation between wallets,
merchant entropy per wallet, temporal concentration, and a Sybil signal for one
nullifier behind many wallets — cannot be computed from a single transaction.
They are properties of the whole visit graph, and without an index they do not
exist.

The evidence is one comparison, reproduced from `data_scientist/train.py`
against its committed synthetic dataset (20,000
visits, 8% fraud, 80/20 stratified split), Gradient Boosting in both rows:

| Graph features computed from | F1-macro | Fraud recall |
|---|---:|---:|
| A reference frozen at training time | 0.8571 | 70.63% |
| A reference refreshed from the indexed visits | 0.9570 | 96.88% |

A Sybil wallet is new by design, so a reference taken once never sees it.
Refreshing that reference from the subgraph is what closes the gap, and it is
why the loader reads the index rather than a snapshot.

The honest limit: those numbers are on synthetic data. The first two real
visits were already read by the model from the live subgraph. On 13
September one wallet claimed at two stores 666 metres apart, 118 seconds apart —
about 20 km/h, faster than walking. It was our own test. Loading those visits
from the subgraph, the model scored the wallet 0.977, above its 0.83 threshold.
The index did not just hold the data the detector needed; it is what let the
detector catch that pattern on its first real input.

Those two visits exercised the rest of the subgraph on real events: the
visitor's nullifier, `distinctMerchants` of 2 and 20 points were all computed in
the mappings, and the `EpochCommitted` the hourly job sent to `FraudOracle` is
indexed and read back by the API to report the epoch as committed.
