<div align="center">

# ZoneGo

**Search for something nearby. Walk there. Get paid for showing up.**

A bodega owner cannot afford advertising that charges by the click.
ZoneGo charges only when a real person walks through their door —
verified with World ID, settled in USDC on Base, in the same second.

`ETHOnline 2026` · `From Scratch` · `Base Sepolia` · `Lower East Side, Manhattan`

</div>

---

## See it in sixty seconds

```bash
git clone https://github.com/ZoneGo-App/ZoneGo.git && cd ZoneGo
docker compose up
```

Open **http://localhost:8000/docs** and try this, in order:

```
GET  /search?lat=40.7190&lon=-73.9882&q=sneakers&radius_km=1
```

Delancey Bodega comes back. **Google files it as a convenience store and
would never show it for "sneakers"** — the owner knows better, and told us.

```
POST /qr/sign        { "campaign_id": 1 }
```

That is the EIP-712 payload the merchant signs. Look at what it does **not**
contain: our server's signature. It never signs.

```
GET  /leaderboard/me?address=0x7A3c9E1b4D2f5A8c6B0e9F7d3C1a5B8e2D4f6A90
```

Points, rank, and how far the next place is — all counted by the chain.

---

## The problem, in numbers

Traditional advertising charges for attention: a click, an impression, a
flyer. None of it guarantees a person in the store. The merchant pays anyway.

| What already happens in the United States | |
|---|---:|
| "Near me" searches per month | **800M** |
| Growth of those searches over two years | **+900%** |
| End in a store visit within 24 hours | **76%** |
| Retail sales still happening in physical stores | **80.4%** |

> **Google knows 76% of those searches end in a visit. The merchant does not.**
> They pay a dollar or two per click and never learn which ones became someone
> standing at their counter. Nobody can audit the platform that bills them.
>
> **ZoneGo makes verifiable exactly what Google can only estimate.**

---

## Why this needs a blockchain

This is the first question a judge asks, and the one that sinks half the
projects. The weak answer is *"we detect fraud"* — Google says that too.

**Our answer is one design decision:**

```
The merchant signs the visit.        ← EIP-712, from their own wallet
The visitor submits the signature.   ← not our backend. the visitor.
The contract verifies it on chain.   ← and pays, without us in the path
```

If our server called `recordVisit()`, our server would decide which visit is
real, and the merchant would have to trust us. The chain would be decoration
and this would be a database with extra steps.

We do run a relay that pays the gas, so someone with an empty wallet can still
claim. **The relay is a convenience, not an authority** — if this service
vanished, the visitor could send the identical call themselves and still get
paid. That is the abandonment test, applied to a real case.

Three parties who do not trust each other, coordinating only through code.

---

## How it works

| Who | Puts in | Takes out |
|---|---|---|
| **Merchant** | USDC per verified visit | A person inside their store |
| **Visitor** | A walk | USDC instantly — no signup, no card, no seed phrase |
| **Protocol** | Infrastructure and indexing | 5% fee, and never custody of the budget |

1. The merchant funds a campaign and sets reward, daily cap, geohash, radius.
2. A visitor searches for `sneakers` within 1, 5 or 10 km.
3. They walk there. The merchant's screen shows a QR carrying an EIP-712
   signature, redrawn every 30 seconds.
4. The visitor submits it. The contract verifies and pays from the vault.
5. The subgraph indexes the event. The fraud model reads the subgraph and
   decides whether the payout is released or **held**.

That last word is why `VisitRecorded` and `RewardPaid` are separate events.
Between them lives the held state — score after the money is gone and the
model decides nothing.

---

## Why it does not get farmed in twenty minutes

Every walk-and-earn scheme dies of fraud. The gates, in the order an attacker
meets them:

| The attack | The gate |
|---|---|
| A thousand wallets, one human | Payment settles against the World ID nullifier, not the wallet |
| The same human in a loop | Payment decays **100 / 50 / 25 / 0** per week at the same store, counted by the contract |
| Claiming twice in a day | Points and payment both need a different day at that store |
| A photographed QR, reused | Single-use nonce, signature dead after 90 seconds |
| Draining a campaign at once | Daily cap, set by the merchant when funding |
| A fraud score nobody can audit | Scores committed on chain as a **Merkle root per epoch** — we cannot rewrite one afterwards to justify a charge |

---

## Zone Explorers

Money brings people in. The game brings them back.

| Action | Points |
|---|---:|
| Verified visit to a store they know | **5** |
| Visit to a store they have never been to | **10** |
| Second visit to the same store, same day | **0** |

Competition is **by zone** — the first six characters of the geohash the
merchant already signs, roughly six blocks. That is deliberate: research on
loyalty programmes is blunt that *forced competition discourages
low-performing users*. Seeing yourself 4,832nd of 5,000 motivates nobody.
Being first on your own blocks is something a person can actually do.

The zone costs nothing: it is already inside the geohash on chain. No map
data, no API, and it works unchanged in any city in the world.

Every point is counted by the subgraph. Anyone can run the same query and get
the same table.

---

## For sponsor judges

Each integration, with the file to open.

<table>
<tr><td width="33%" valign="top">

### 🌍 World

**Without it there is no product.** A network paying for physical visits has
one way to die: one person with a hundred wallets emptying a campaign in an
hour. Selfie Check turns *a wallet* into *a person*.

The nullifier binds to the visitor's Privy wallet and is stored in
`VisitRegistry`. The contract rejects a second claim from the same nullifier
in the same campaign inside the window — **risk and eligibility, which is
literally what the prize asks for**, not a login button.

`subgraph/schema.graphql` → `Visitor.nullifierHash`
`api/routers/visits.py` → the claim path
`feedback/world.md` → our feedback

</td><td width="33%" valign="top">

### 🔐 Privy

**Without it this is a demo for crypto people.** Our users are the woman who
runs the bodega and the neighbour buying bread. Neither will install an
extension or write twelve words on paper.

The merchant signs in with email, gets an embedded wallet, funds a campaign.
The visitor signs in with a phone number, gets a wallet, gets paid. A complete
B2B2C financial flow where **neither side knows there is a blockchain
underneath.**

`api/config.py` → chain config, Base Sepolia
`feedback/privy.md` → our feedback

</td><td width="33%" valign="top">

### 📊 The Graph

**Without it the model has nothing to read.** Visit history lives in on-chain
events; the fraud model needs it, and so does the merchant's audit.

The subgraph indexes campaigns, visits, rewards and epochs, and computes
points and zones in the mappings. `Visitor.distinctMerchants` — how many
different stores someone found — **is impossible to compute without an index
of the chain.** That is the technical argument, not a slogan.

`subgraph/schema.graphql` → the entities
`subgraph/src/visit-registry.ts` → scoring
`api/subgraph.py` → the GraphQL client
`feedback/the-graph.md` → our feedback

</td></tr>
</table>

Hedera and x402 were evaluated despite the prize, and dropped: a second chain
would have split the technical story in two. With nine days, coherence beats
coverage.

---

## Repository

```
api/          FastAPI — search, QR signing, relay, scoring, leaderboard
  eip712.py     the payload the merchant signs. the server never signs it
  geo.py        geohash and distance, no dependencies
  points.py     the scoring rules, mirrored from the subgraph
  subgraph.py   GraphQL client with a short cache
subgraph/     The Graph — schema, ABIs, manifest, AssemblyScript mappings
schema/       the event contract agreed between all four roles
feedback/     sponsor feedback documents
contracts/    Solidity — on branch feat/contracts-skeleton
```

### Running it

```bash
docker compose up                    # then localhost:8000/docs
```

<details>
<summary>Without Docker</summary>

```bash
python -m venv .venv
.venv/Scripts/activate               # source .venv/bin/activate on macOS/Linux
pip install -r api/requirements.txt
uvicorn api.main:app --reload
pytest -q
```
</details>

<details>
<summary>The subgraph</summary>

```bash
cd subgraph
npm install
npx graph codegen && npx graph build
npx graph deploy zone-go
```
</details>

The service starts in **mock mode** and answers with sample campaigns around
Delancey and Orchard, so the frontend can be built before any contract exists.
`/health` reports which mode it is in, and so does the startup log — a
deployment left on mock answers 200 to everything and looks perfectly healthy
while serving invented data.

### API

| | |
|---|---|
| `GET /health` | Status, and whether mock mode is on |
| `GET /search` | Stores near a point, by radius and free text |
| `GET /campaigns` | Campaigns, read from the subgraph when live |
| `POST /qr/sign` | The EIP-712 payload a merchant signs |
| `POST /visits/claim` | The relay — submits a claim and pays the gas |
| `POST /score` | Fraud score, plus the three features behind it |
| `GET /leaderboard` | Explorers and merchants, by zone or by week |
| `GET /leaderboard/me` | One player's points, rank, and gap to the next |

---

## Status

Honest, because a judge will find out anyway.

| | |
|---|---|
| API — 9 endpoints, **78 tests** | Running |
| Subgraph — schema, ABIs, manifest, mappings | Compiles; deploy pending contract addresses |
| Contracts | Interfaces and events; logic in progress |
| Public deployment | Pending |

**Known and deliberate:** the fraud model trains on synthetic data with four
injected patterns. `ml/DATA.md` documents why they are synthetic, which fraud
literature each pattern comes from, and how real data swaps in without
changing the pipeline. A weakness you name first stops being an attack and
becomes rigour.

---

## AI attribution

ETHGlobal asks for this explicitly. It is written as the work happens, not
bolted on at the end.

The nine-day plan, the choice of three sponsors and the architecture of a
visit were worked through with an AI assistant, from the transcripts of the
official workshops and the prize pages. **The correction that takes the
backend out of the trust path** — the merchant signs, the visitor submits —
came out of reviewing the first architecture for points of centralisation.

| Person | Where AI helped | What they decided by hand |
|---|---|---|
| Sebastián | Contract scaffolding, Foundry tests, EIP-712 syntax | Authorisation logic, order of validations, revert conditions |
| Lucio | API structure, subgraph mappings, deployment config | Event schema, epoch rotation, rate-limit policy |
| Edmer | Synthetic generator, plotting code, pipeline skeleton | Feature choice, PR-curve threshold, reading the metrics |
| David | UI components, library integration, loading states | User journey, information hierarchy, error messages |

**Why the line sits there.** AI writes scaffolding, syntax and repetitive
code. The decisions that determine whether the system is *correct* — who has
authority to authorise a payment, which feature enters the model, where the
threshold sits — are made by people and recorded with their reasoning.

The history shows it: small, frequent commits from four authors, with messages
that say why. And every figure here comes from a script anyone can run against
this repository and get the same number.

> *You can outsource your thinking, but you cannot outsource your
> understanding.* — Austin Griffith, ETHGlobal workshop

All four of us can explain any line of this project.

---

## License

MIT

