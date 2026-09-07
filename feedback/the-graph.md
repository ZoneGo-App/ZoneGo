# Feedback for The Graph

## What we integrated

A subgraph on base-sepolia indexing three contracts — `CampaignVault`,
`VisitRegistry` and `FraudOracle` — into ten entities. Deployed to Subgraph
Studio as `zone-go` v0.0.1.

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

## Why The Graph was necessary, not decorative

The graph features our fraud model relies on — co-visitation degree between
wallets, merchant entropy per wallet, temporal concentration per campaign —
cannot be computed without an index of the chain. The measured improvement
between the baseline model and the graph-feature model is the evidence.

_(numbers pending — Edmer)_
