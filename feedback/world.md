# Feedback for World — Selfie Check

Mateo Sauton, in the ETHOnline workshop: *"don't be nice."* We took him at his
word. Everything below happened to us while building ZoneGo, and the code it
refers to is in this repository.

The four sections that follow match the four things the Selfie Check prize asks
this document to cover.

## What we built

ZoneGo pays people in USDC for walking into small stores. A network that pays
for physical visits has one way to die: one person with a hundred wallets
emptying a campaign in an hour. Selfie Check is what closes that door, so it is
an abuse-prevention signal in the most literal sense — it decides whether a
payout happens at all.

The flow, end to end:

1. **Frontend** (`frontend/ZoneGoApp/src/screens/IdentityCheck.tsx`) opens IDKit
   with `useIDKitRequest`, the `selfieCheckLegacy({ signal: visitorAddress })`
   preset and `environment: 'production'`. The signal is the visitor's wallet,
   so a proof cannot be replayed for a different address.
2. **`GET /world/rp-context`** (`api/rp_signature.py`) signs the relying-party
   request. World ID 4.0 refuses unsigned requests and the signing key must not
   reach a browser, so the signature has to come from our backend.
3. **`POST /world/verify`** (`api/world.py`) forwards the IDKit response to
   `developer.world.org/api/v4/verify` and gets the nullifier back.
4. The backend signs an **EIP-712 attestation** naming the wallet and the
   nullifier. The attester address is published at `/world/attester`.
5. **`VisitRegistry.claim()`** recovers that signature against its immutable
   `TRUSTED_ATTESTER`, burns the attestation on first use, and writes
   `nullifierBoundTo[nullifier] = wallet`. From then on that human is bound to
   that wallet and can never claim through another one.
6. Payment decays 100 / 50 / 25 / 0 % for the same human at the same store in
   the same week, keyed by nullifier rather than by wallet.

Step 4 exists only because of the gap described under *Missing*, below.


## 1. Selfie Check docs and integration flow

**Selfie Check only exists as a "legacy" preset.** World ID 4.0 is the current
protocol, and it is what the RP signature and the v4 verify endpoint speak. But
the only way we found to request Selfie Check is `selfieCheckLegacy()`, a World
ID 3.0 preset. The name reads as deprecated, and nothing we found said whether
building on it today is safe or what replaces it. We shipped on it because
there was no alternative, not because we were confident in it.

**RP request signing had to be reimplemented from the spec.** Our backend is
Python. We implemented the signed message —
`version(1) || nonce(32) || created_at(8, big-endian) || expires_at(8,
big-endian) || action(32)`, EIP-191, recoverable secp256k1, with the action run
through `hash_to_field` (keccak256 shifted right by 8 bits) — and pinned it to
World's published test vectors (`api/tests/test_rp_signature.py`). Those
vectors are the reason this worked at all; without them there was no way to
tell a correct signature from one World would silently reject. A server-side
reference implementation outside JavaScript would have saved real time.

**`environment: 'production'` is required for Selfie Check.** It is easy to
assume a hackathon build belongs in staging, and the distinction is worth
stating wherever Selfie Check is introduced.


## 2. Developer Portal: navigation, discovery and debugging

**The action has to match in three places, and nothing checks that for you.**
The action must exist in the Developer Portal, be passed to the IDKit widget,
and be covered by the RP signature. If any of the three disagree the proof
fails, and the failure does not say which one is wrong. We now check the action
twice in `api/world.py` — before calling World, and again on World's answer.

**The action check is a security boundary, and the docs could say so.** A
person's nullifier is different for every action. An integration that accepts a
valid proof for *any* action under the app lets one human bind one wallet per
action — which, in a product that pays per human, is exactly the attack Selfie
Check is there to stop. We only saw this because we were thinking about
farming. A single sentence in the docs would save someone who is not.

**The 400 bodies from the verify endpoint are genuinely useful.** Reasons like
"already verified", "expired" and "wrong action" are the part that lets an app
tell a person what to do next. We pass them through instead of flattening them
into a generic failure. This is the best debugging aid in the whole flow.

**A pasted signing key fails opaquely.** Our RP signing key arrived mangled when
pasted into our hosting dashboard, and request signing started failing. The message
was our own (`not a valid 32-byte key`), and it took comparing key lengths to
find. Stating the exact expected format — `0x` followed by 64 hex characters —
next to wherever the portal displays the key would shorten that.

> _TODO (Lucio): what the Developer Portal showed when creating the
> `verify-visitor` action, and anything that was hard to find while setting up
> the app and its RP id._


## 3. Proof flows, errors and edge cases

**The `rp_context` nonce is single use and expires in 300 seconds.** A retry
that reuses the same context fails. Each attempt needs a freshly signed one, so
`IdentityCheck.tsx` fetches a new `rp_context` and remounts the widget whenever
World rejects a check. Reasonable once known; not obvious from the widget, which
looks as if it can simply be retried.

**The verify endpoint can return a nullifier with fewer than 64 hex digits.**
World pads nullifiers to 64 digits itself inside the developer portal
(`web/api/helpers/verify.ts`). An integrator who signs the value as received
hits a quiet trap: `encode_typed_data` pads a short `bytes32` without saying so,
so the attestation is signed over one value and reported with another, and the
mismatch only surfaces after the signature already exists. We normalise before
signing (`normalize_nullifier` in `api/world.py`). Returning it already padded,
or documenting that it may not be, would remove the trap.

**A success without a nullifier is treated as a failure.** The nullifier is the
whole point of the exchange, so we refuse rather than attest to nothing.

**The Sandbox App.** In the ETHGlobal feedback session we watched other teams hit
the same walls, which is worth reporting even though it did not happen to us
first: a QR code that opened the app store instead of the Sandbox App (their
workaround was prefixing the link with `sandbox`), and several teams unable to
complete Selfie Check at all who fell back to the simulator.

> _TODO (Sebastián, David): Sandbox App states you saw while testing, how test
> users were set up, and any proof that failed in a way the error did not
> explain. This is the part the prize asks about most directly, and it is
> yours — you wired IDKit._


## 4. What was confusing, missing, broken, or hard to test

**Missing — a way to verify Selfie Check on chain outside World Chain.** This is
the largest gap we hit, and it shaped the architecture. The World ID Router
verifies Orb credentials only (`groupId` 1), and the v4 verifier is deployed on
World Chain. Our contracts are on Base. So `VisitRegistry` cannot ask World
anything about a Selfie Check, and there is no proof artifact to hand it.

The only way through was a trusted attester: our backend asks World, then signs
an attestation the contract believes. It is the single trust assumption in
ZoneGo — everywhere else the merchant signs and the chain decides, and here the
contract takes our word. We state it in our README rather than hide it, but we
would rather not have it. A Selfie Check verifier on Base, or a cross-chain
attestation World signs itself, would remove it entirely.

**Confusing — "legacy" as the name of the current path.** Covered above; it
belongs on this list too.

**Hard to reason about — how long a Selfie Check should count.** See the next
section.


## On the 90-day expiry

Mateo confirmed a Selfie Check verification is not permanent: it caps at 90
days. What that meant for our design:

- **An attestation lives one hour.** It has to survive the walk between
  verifying at home and scanning a QR at the counter. We started at two
  minutes, and people would have arrived to find it expired.
- **An attestation is good for one claim.** `VisitRegistry` burns it on first
  use, so a longer lifetime would buy nothing.
- **A selfie counts for fifteen days from the visitor's last visit.** Because
  the contract already records `nullifierBoundTo` on the first claim, and that
  binding cannot move, `GET /world/attestation/{visitor}` can issue a fresh
  attestation for someone the chain has already seen — restating a public fact
  rather than vouching for a new one. Fifteen days sits well inside World's 90.

The honest limit: we measure the window from the last visit, not from the
moment of verification, because we keep no record of the second and the chain
keeps the first. That errs toward asking for a selfie sooner, never later.


## What worked well

- **The RP signature test vectors.** They made a from-scratch reimplementation
  in another language verifiable, which is the whole difference between
  "probably right" and right.
- **Actionable error reasons** from the verify endpoint.
- **The nullifier model itself.** Stable per human, different per action,
  revealing nothing about the person. It gave us one human, one payout, without
  storing a single piece of identity.
- **Direct answers in the workshop and on Discord**, including the 90-day
  expiry, which we would not otherwise have known to design around.


## User feedback

> _TODO (team): from real test sessions — how the Selfie Check felt, where
> someone hesitated, and how long it took in seconds from opening the widget to
> a verified result._

---

**Authors:** Lucio, Sebastián, Edmer, David
**World contact:** MrSauron (Discord)
