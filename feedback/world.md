# Feedback for World — Selfie Check

Living document. Each of us writes on the same day it happens, not from memory at the end.
Mateo Sauton, in the ETHOnline workshop: *"don't be nice."*

## What we integrated

**Backend, as of Sept 7 — Lucio.** The claim path carries the nullifier from the
visitor's phone through our relay into `VisitRegistry`, which is what enforces
one claim per person per campaign inside the window. In live mode the API
refuses a claim with no nullifier rather than defaulting it to zero: a zero
would put every visitor in one weekly bucket, so the second person to claim
anywhere would be paid 50% of what was actually their first visit.

The API does not verify the Selfie Check proof itself — it accepts the proof
field and passes the nullifier on. Real verification lands with the contract.

_(SDK integration and the verification flow — pending, David and Sebastián)_

## Developer feedback

### What worked well

### What took longer than it should have

### Documentation: what was missing or wrong

### Bugs we hit

| Date | What we did | What we expected | What happened |
|---|---|---|---|
| | | | |

## User feedback

### How the verification flow felt

### Where someone hesitated or got stuck while testing

### How long it takes, in seconds

## What we wished existed

## On the 90-day expiry

Mateo confirmed Selfie Check verification is not permanent — it caps at 90 days.
What that meant for our design:

_(pending)_

---

**Authors:** Lucio, Sebastián, Edmer, David
**World contact:** MrSauron (Discord)
