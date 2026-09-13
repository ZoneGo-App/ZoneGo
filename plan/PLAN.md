# ZoneGo — Execution plan · 9 days

**ETHOnline 2026 · From Scratch track · Base Sepolia · Team of four**
State as of **Monday 7 September — day 4**. Deadline: **Sunday 13, 12:00 ET**.

> **This is a snapshot, kept as the record of how the work was planned and
> split.** It was written on day 4 and has not been updated since, except to
> translate it. It is not the current state of the project: for that, read the
> *Status* section of the [README](../README.md). Some assumptions below turned
> out to be wrong once checked — Privy organization wallets were not required.
> Prize amounts and weightings the original carried have been left out of the
> translation, because they did not match the prize pages; the requirement
> tables are kept as the team read them on day 4.

The hackathon started on Friday 4 September at 12:00 ET. Every day closes with a
milestone that can be checked: **if it cannot be demonstrated, the day is not
closed.** ✔ marks what could be demonstrated on the day this was written.

---

## The product

The neighbour searches for something nearby, walks to the store, scans a QR and
gets paid. The merchant pays only when a unique, verified human walks through
the door, and can audit every payment against the chain without trusting us.

**The decision everything rests on:** the merchant signs the visit with EIP-712
from their own device, the neighbour submits that signature to the contract, and
the contract verifies it on chain. Our server pays the gas as a convenience, not
as an authority.

Three sponsors, none of them removable: **World** (unique human), **Privy**
(wallets without a seed phrase), **The Graph** (auditable history).

---

## The four roles

| Person | Domain | Owns | Delivers to the team |
|---|---|---|---|
| **Sebastián** | Contracts and Web3 | `CampaignVault`, `VisitRegistry`, `FraudOracle`, EIP-712 verification, World ID integration, Foundry tests | ABIs, deployed addresses, green tests |
| **Lucio** | Services and infrastructure | FastAPI API, subgraph, epoch service and Merkle tree, deployment, monitoring, CI | Documented endpoints and the subgraph URL |
| **Edmer** | Data science | Synthetic generator, features, fraud model, category classifier, attack simulation, metrics | A served model and a reproducible metrics table |
| **David** | Frontend and product | Neighbour app, merchant panel, Privy integration, QR scanner, World flow | A navigable demo and the submission screenshots |

**The Sebastián / Lucio boundary.** Everything that compiles to bytecode is
Sebastián's. Everything that runs on a server is Lucio's. The subgraph is
Lucio's because it is TypeScript and queries, not Solidity.

**The rule that prevents blocking.** The event schema is frozen in
`schema/events.md`, and nobody changes it without all four agreeing.

---

## What was standing on day 4

### Chain — Base Sepolia

The contracts deployed at the time were redeployed on 12 September. The current
addresses and the subgraph URL are in the README, and listing old ones here
would only give a reader two sets to choose between.

### Branches

| Branch | Commits ahead of `main` | Contents |
|---|---|---|
| `feat/api-base` | 57 | API with 12 endpoints, 164 tests, subgraph |
| `feat/contracts-skeleton` | 11 | Three contracts, deployed, 4 tests |
| `feat/data-scientist` | 2 | Generator, event schema, training |
| `main` | — | **A single file: `README.md`** |

---

# DAY 1 — Friday 4 September
## Foundations, the data contract, and the chain decision

**Focus.** Freeze the event schema so all four can work in parallel, and give
the repository a real history from the first hour.

### Sebastián — contracts and Web3
- ✔ GitHub organization and a public repository with an MIT license,
  `.gitignore` and an initial README. Linked in the ETHGlobal dashboard.
- ✔ Foundry in `/contracts`. Interfaces and events for the three contracts.
- ✔ The EIP-712 `struct` for a visit and its typehash — the contract between
  the QR and the chain.
- ✔ The chain is **Base Sepolia**: World ID Router at
  `0x42FF98C4E85212a5D31358ACbFe76a621b50fC02`, The Graph indexes it as
  `base-sepolia` (chainId 84532), Privy is chain-agnostic.

### Lucio — services and infrastructure
- ✔ CI on GitHub Actions: tests run on every push and every PR.
- ✔ FastAPI skeleton in `/api` with `/health`, Pydantic and `docker-compose`.
- ✔ A mock server on the frozen schema, so David does not have to wait.

### Edmer — data science
- ✔ `generate.py`: merchants with real opening hours and coordinates on the
  Lower East Side (40.7220 / −73.9870), neighbours, and labelled visits.
- ✔ Four injected fraud patterns: impossible travel, systematic co-visiting,
  out-of-hours bursts, repeated claims under different nullifiers.
- ✔ Fraud rate at 8%, imbalanced on purpose.

### David — frontend and product
- ✗ Next.js 14 scaffold with TypeScript and Tailwind.
- ✗ `@privy-io/react-auth` with email and phone login, showing the embedded
  wallet's address.

**Closing milestone.** Public repository linked, with commits from four authors.
Chain decided. `forge build` compiles. CI green. Privy login working.
`docker compose up` starts the API. 20,000 labelled visits in a CSV.

---

# DAY 2 — Saturday 5 September
## Campaigns on chain and a model baseline

**Focus.** A merchant can create and fund a campaign on testnet, and there is a
number to measure the model against for the rest of the week.

### Sebastián — contracts and Web3
- ✔ `CampaignVault.sol`: `createCampaign(rewardPerVisit, dailyCap, geohash,
  radius)`, `fund()` with test USDC, `withdraw()` of the remainder.
- ✔ Tests for the failure paths: funding a campaign that does not exist,
  withdrawing without being the owner, exceeding the daily cap.
- ✔ Deploy to testnet.

### Lucio — services and infrastructure
- ✔ Campaign reads against the node, with a cache. A typed contract client.
- ✔ `POST /qr/sign`: the server builds the EIP-712 payload **but does not sign
  it** — the merchant signs with their own wallet.

### Edmer — data science
- ✔ Features v1: time since the same nullifier's previous visit, implied speed
  between stores, deviation from the modal hour, co-visit degree.
- ✔ Balanced logistic regression and gradient boosting, against the trivial
  baseline.
- ✔ Macro F1 and recall on the fraud class. **Recall is the metric that
  matters:** letting fraud through costs the merchant money.

### David — frontend and product
- ✗ Campaign creation screen: category, reward, budget, daily cap and radius on
  a map.
- ✗ Connect to the contract with `wagmi` + `viem`, signing with the Privy wallet.

**Closing milestone.** A campaign created and funded with test USDC, visible in
the explorer with its hash. A comparison table of two models with macro F1.

---

# DAY 3 — Sunday 6 September
## The full loop, and the backend out of the trust path

**Focus.** A visit ends in a real USDC transfer on testnet, with the contract
verifying the merchant's signature. The most important day of the nine.

### Sebastián — contracts and Web3
- ✔ `VisitRegistry.claim(...)`: verifies **on chain** the merchant's EIP-712
  signature, its validity window, the nullifier and the daily cap. Transfers
  and emits.
- ✔ A single-use nonce per merchant, recorded on chain.
- ✔ **The decaying curve in the contract**: 1st visit 100%, 2nd 50%, 3rd 25%,
  4th 0, per week. **The contract calculates it, not the server** — if the
  backend decides it, we are an authority again and the answer to the judges
  falls apart.

### Lucio — services and infrastructure
- ✔ A transaction relay, documented as optional: the neighbour can submit the
  signature themselves.
- ✔ `GET /search?q=&lat=&lon=&radius=` — the product's front door. Filter by
  category and by words in what the merchant declared they sell, plus distance.
  No model. Radius of 1, 5 or 10 km.
- ✔ `POST /score` returning a score and the three features that weighed most.

### Edmer — data science
- ✔ Fix the generator: geography moved to New York (sigma 0.008), a stable
  nullifier per wallet, and impossible travel that actually moves the visitor.
- ✔ Rewrite the feature pipeline to consume **the event schema**, not the CSV.
- Category classifier from the free-text description — TF-IDF and logistic
  regression.

### David — frontend and product
- ✗ Search bar and radius selector. The app's first screen.
- ✗ Results on an embedded Google map, each merchant showing what it pays today.
- ✗ Places autocomplete when a merchant signs up, storing the `place_id`.
- ✗ QR scanner with `html5-qrcode` and payment confirmation.
- ✗ Merchant screen generating the signed QR, **regenerated every 30 seconds**.
  The signature lasts 90, so a slow scan does not fail.

**Closing milestone.** The full loop on testnet: search "sneakers", see
merchants in range, generate a signed QR, scan, claim and receive USDC. The hash
of that first transaction goes into the README.

---

# DAY 4 — Monday 7 September · TODAY
## The subgraph: The Graph as the source of truth

**Focus.** Move every history query off our own store and onto the subgraph.
**Project Check-in #1, 23:59 ET.**

### Lucio — services and infrastructure
- ✔ `schema.graphql` with Campaign, Visit, Merchant and Visitor and derived
  relationships. Ten entities.
- ✔ AssemblyScript mappings and **deployment to Subgraph Studio**. Entities
  aggregated by hour and by merchant.
- ✔ Every history read in the API goes through GraphQL.

### Sebastián — contracts and Web3
- ✔ `CampaignCreated` emits geohash and radius. **The last window to touch the
  schema.**
- ✔ Redeploy the three contracts, with `FraudOracle` in `DeployAll.s.sol`.
- ✔ Start `FraudOracle.sol`: the signatures of `commitEpoch` and `verifyScore`.

### Edmer — data science
- ✗ **[HARD REQUIREMENT]** A GraphQL client against the subgraph. Today
  `load_events_from_subgraph()` is a stub. **The URL is published and answers.**
- ✗ Features that can *only* be calculated with the indexed graph: entropy of
  visited merchants and temporal concentration per campaign.
- ✗ Retrain, measure the improvement over the day 2 baseline, and commit the
  table.
- Always return the three features that weighed most.

### David — frontend and product
- ✗ Merchant panel reading from the subgraph: visits per hour, real cost per
  visit, remaining budget.
- ✗ Empty and loading states in every view.

> **The requirement that disqualifies a prize.** The Graph requires, verbatim,
> *"consume live data, not mocked or local datasets"*. The CSV is for training;
> inference in the demo runs against the subgraph, or we are out of the prize.

**Closing milestone.** Subgraph deployed and queryable at a public URL. The
panel is fed only by GraphQL. Model metrics before and after the graph
features.

---

# DAY 5 — Tuesday 8 September
## World ID and the fraud oracle on chain

**Focus.** Close the Sybil hole and bring the model's output on chain. Mentor
feedback session, 14:00 to 16:00 ET.

### Sebastián — contracts and Web3
- Integrate **World Selfie Check** with the Sandbox App. The `nullifierHash` is
  bound to the Privy wallet. Today `VisitRegistry.claim` has verification as a
  `TODO`: it accepts the nullifier without checking it against World's router.
- **Risk-based flow, not flat verification:** Selfie Check unlocks small rewards;
  high rewards require Orb or Official ID.
- **Revalidation at 90 days** — a Selfie Check verification expires.
- Finish `FraudOracle`: `commitEpoch(bytes32 root, uint64 epoch)` **with access
  control**, and `verifyScore(address, uint16, bytes32[] proof)`. Today both are
  `revert("not implemented")`.
- Confirm the leaf format of the tree:

```
leaf = keccak256(keccak256(abi.encode(address wallet, uint16 score)))
node = keccak256(a + b), with the pair sorted
```

  The score is in basis points, 0 to 10,000 (0.7213 → 7213), because
  `verifyScore` takes a `uint16`. It fits OpenZeppelin's `MerkleProof.verify`
  unchanged. Without access control on `commitEpoch`, anyone can publish a root
  and the whole audit argument collapses.

### Lucio — services and infrastructure
- ✔ The leaderboard, as a subgraph query. `GET /leaderboard`: 5 points per visit,
  10 if the merchant is new, 0 for the same store on the same day. Weekly and
  all-time. **The chain counts the points, not our store.**
- ✔ Competition by zone: the first six characters of the geohash the merchant
  already signs, about six blocks. No map data, no API.
- ✔ Personal panel. `GET /leaderboard/me`: your own points, how many play in that
  zone, and how many you need to pass the one above.
- ✔ Merkle tree over (wallet, score) pairs.
- ✔ Epoch service and proof endpoint: `GET /epochs/current`,
  `GET /epochs/{n}`, `GET /epochs/{n}/proof`.
- Publish the root on chain every hour, as soon as `commitEpoch` exists.
- World **Sybil Score** endpoint — waiting on permission from World.

### Edmer — data science
- Close day 4 first: inference against the subgraph and the graph features.
- Replace `wallet_score()` in `api/routers/score.py`: it returns a float from 0
  to 1 and nothing else — the API converts it to basis points and puts it in the
  tree.
- Add World's **Sybil Score** as a feature, combined with the co-visit features
  from the subgraph.
- Set the threshold from the precision-recall curve, not by eye.
- Prepare the answer to "what happens if the model is wrong?": holding is
  reversible and the neighbour can appeal.

### David — frontend and product
- **Everything pending from days 1 to 4** — it is the project's critical path.
- World verification flow with pending, verified and rejected states.
- Leaderboard screen — Zone Explorers. Weekly table, your position, and the
  history of merchants discovered.
- Second table: the most visited merchants in the neighbourhood. From the same
  subgraph.
- Merchant fraud panel: held visits, score, and the features that explain it.
- Present at the 14:00 ET feedback session.

**Closing milestone.** An unverified neighbour cannot get paid, demonstrable on
testnet. A Merkle root published for at least three epochs. A Merkle proof
verified on chain from the panel.

---

# DAY 6 — Wednesday 9 September
## Hardening: break it before a judge does

**Focus.** Attack the system on purpose and measure what holds. The day that
separates a prototype from a product.

### Sebastián — contracts and Web3
- Replay protection: a QR photographed and used two minutes later must revert.
  **Write the test that proves it.**
- A rate limit per nullifier and per campaign. An emergency pause for the
  campaign owner.

### Lucio — services and infrastructure
- API rate limiting, monitoring and alerts.
- Structured logging of every rejected claim and why.

### Edmer — data science
- Simulate three attacks and measure detection: a farm of thirty verified
  wallets, a merchant visiting itself, collusion between two neighbouring
  merchants.
- Document the detection rate for each in a table.

### David — frontend and product
- Privy **organization wallets** for the merchant, not personal ones. Believed at
  the time to be a verbatim requirement of the B2B prize.
- **Transfer policy:** the campaign balance can only leave as visit rewards,
  with a daily cap.
- Merge campaign creation and the panel into a single "My Panel" view that
  changes with the role, with a status column: paid, held, with the score.
- Visible errors with a way out: expired QR, out of range, already claimed
  today, verification pending.
- Truly responsive: the app is used on the street, on a phone, one-handed.

**Closing milestone.** A Foundry test proving a reused QR reverts. A table of
three attacks with their detection rates. App usable on a phone.

---

# DAY 7 — Thursday 10 September
## Public deployment and demo data

**Focus.** Anyone with the link can use ZoneGo without us present. A hard
requirement to be a finalist. Second feedback session, 09:00 to 11:00 ET.
**Project Check-in #2, 23:59 ET.**

### Lucio — services and infrastructure
- Deploy the API to production with a domain and HTTPS. Environment variables
  kept out of the repository. Today there is a `Dockerfile` and
  `docker-compose.yml` but **no destination chosen**.
- Leave the epoch job running automatically and monitored.
- README with the three contract addresses, the subgraph URL and how to run
  everything locally.

### Sebastián — contracts and Web3
- Seed three demo campaigns with recognisable merchants and enough balance for a
  judge to try them without draining them.
- Verify the three contracts in the explorer and link them from the README.

> **And this cannot wait until Thursday.** The chain is empty: nobody has called
> `createCampaign`. Without a real campaign there is no demo, the subgraph has
> nothing to index, and The Graph sees no live data. One call unblocks all three.

### Edmer — data science
- Write the feedback documents the prizes require. `the-graph.md` already has
  what the subgraph cost and what worked, and waits for the numbers of the base
  model against the model with graph features. `world.md` has the backend part.
  Still missing: all of `privy.md`, and the SDK and verification-flow sections
  of World's.

### David — frontend and product
- Deploy the frontend to Vercel with its own domain.
- **Demo mode:** a button that simulates being at the store, so a judge in
  another country can complete the journey without travelling to Manhattan.
- The three screenshots and the cover image for the submission.

**Closing milestone.** A public URL tested from a device that never touched the
project. Three seeded campaigns with balance. Feedback documents committed.

---

# DAY 8 — Friday 11 September
## The video and the draft submission

**Focus.** The video is the round 1 filter and what the sponsors watch. It gets
made today, with two days of margin.

### The whole team — all four
- A script of **3 minutes 30, timed**: 25 s of problem, 2 min of live
  demonstration of the full journey, 40 s of architecture with the on-chain
  score, 25 s on the three integrations.
- Record in 1080p, clear voice, **no music and no speed-up**. Between 2 and 4
  minutes, a hard cut: the system checks the file and rejects it if it does not
  comply.
- Upload and wait for the green verification marks.

### Lucio and Edmer — services + data
- Main README: what it is, how it works, measured metrics, and the AI
  attribution section ETHGlobal explicitly asks for.
- Copy the planning documents into `/plan`.

### Sebastián and David — chain + frontend
- The long description of the submission. The more detail, the easier it is to
  evaluate.
- The three prize applications, with the exact file, line and function of each
  integration.

**Closing milestone.** Video uploaded and verified. Submission saved with the
three applications filled in. The project is already submitted; what remains is
making it better.

---

# DAY 9 — Saturday 12 September
## Margin, polish, and resubmission

**Focus.** No new development. Today only what is broken gets fixed and what
exists gets polished.

### The whole team — all four
- Walk the full flow three times from three different devices, one on a network
  that has never tried it.
- Check the repository is still public and the deployment is up.
- Rehearse the answers to the five questions the judges are likely to ask, with
  the number at hand.

### Sebastián and Lucio — chain + infra
- The addresses in the README match the deployed ones. Subgraph synced, with no
  indexing errors.

### Edmer — data science
- The figures in the README match the latest run. **A metric that cannot be
  reproduced is worse than not having one.**

### David — frontend and product
- A last pass on the interface: nothing misaligned, nothing half translated,
  nothing broken on a phone.

**Closing milestone.** Project resubmitted with the final version, 20 hours
before the deadline. All four have tested the public link from their phones.

---

## What is open

### Merging to `main` — all four
`main` has a single file. It is what anyone opening the repository sees, and
what ETHGlobal's automated check looks at. Three branches with 70 commits
between them sit outside it. The longer it waits, the more the merge costs.

### Where the merchant's name and what they sell live — decision pending
The chain stores geohash, reward, cap and radius: not the name, nor the free
text of what the merchant sells. That text is what makes search work, and search
is the product's front door and the first move of the demo. Against the chain,
`/search` has nothing to search on. Proposal: IPFS, with the hash inside
`CampaignCreated` — a decision with a cost in the contract.

### A relay wallet with test ETH — Lucio
The relay is written and tested against a simulated RPC, but has never sent a
real transaction. `RELAY_PRIVATE_KEY` is empty.

### Waiting on World
Permission for the Sybil Score is still unanswered. It blocks Edmer's feature
and Lucio's endpoint, not the rest of the integration.

---

## Hard requirements, with owner and day

### ETHGlobal — disqualifies the whole project

| Requirement | Who | Day | If missing |
|---|---|---|---|
| Public repository for the whole event | Sebastián | done | Disqualification |
| A real, incremental commit history | All four | every day | Round 1 filter |
| No code from before 4 September | All four | done | Disqualification |
| Deployed and usable without us present | Lucio + David | 7 | No finalist |
| Video of 2–4 min, 720p, no music, no speed-up | All four | 8 | Automatic rejection |
| Submit at least once before Sunday 12:00 ET | One person | 8 | No prizes |
| **Project Check-in #1 — Monday 7, 23:59 ET** | One person | **today** | Deposit lost |
| Project Check-in #2 — Thursday 10, 23:59 ET | One person | 7 | Deposit lost |
| AI attribution section in the README | Lucio + Edmer | 8 | Risk of disqualification |
| All four at round 2: Monday 14, 12:00–14:00 ET | All four | — | Automatic disqualification |

### World — as understood on day 4

| Requirement | Who | Day |
|---|---|---|
| Selfie Check integrated and working end to end | Sebastián | 5 |
| Used as a risk signal, not as a plain login | Sebastián | 5 |
| Sybil Score as a model feature | Edmer | 5 |
| 90-day revalidation accounted for | Sebastián | 5 |
| Feedback document | All four | 1 to 7 |

### Privy — as understood on day 4

| Requirement | Who | Day |
|---|---|---|
| Privy as a core component, not an accessory | David | 1 to 5 |
| At least one Privy wallet working | David | 1 |
| Organization wallets for the merchant | David | 6 |
| At least one control: a transfer policy with a cap | David | 6 |
| A real financial transaction completed | Sebastián | 3 |
| Explain how Privy improves the product | All four | 8 |

### The Graph — as understood on day 4

| Requirement | Who | Day |
|---|---|---|
| Subgraph deployed and publicly queryable | Lucio | ✔ 4 |
| Live data: inference runs against the subgraph | Edmer | 4 |
| Graph features impossible without an index, with the improvement measured | Edmer | 4 |
| Return the reasoning, not just the raw result | Edmer | 4 |
| Leaderboard by visits, as a subgraph query | Lucio | ✔ 5 |

---

## The order of sacrifice

If something falls over, it is written down in advance:

**Payment loop → subgraph and model → leaderboard → trivia.**

If the payment loop fails in the demonstration, nothing else matters. A jury
forgives a missing feature; it does not forgive a demo that does not work.

**The feedback documents are never sacrificed:** they are written while
integrating, and do not take a block of time of their own.
