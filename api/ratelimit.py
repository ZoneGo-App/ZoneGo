"""How often one caller may ask, per route, and why the numbers differ.

Not every endpoint costs the same. A search is a cached read; a claim spends our
own testnet ETH on gas, and a World verification burns quota on somebody else's
API. Putting one number on all of them would either leave the expensive paths
open or throttle the cheap ones for no reason.

So the limits follow the cost:

    /visits/claim    strict — every call can spend gas, whether it succeeds
                     or reverts, and a loop here empties the relay wallet
    /world/verify    strict — each one is a request against World's quota
    /qr/sign         moderate — cheap for us, but a signature per second from
                     one address is not a person standing in a shop
    everything else  generous — reads, and the subgraph cache absorbs them

Keyed by IP and held in this process. Behind two replicas each would keep its
own count, so the real ceiling doubles. Said out loud rather than papered over:
the durable version needs Redis, and a shared store is not worth standing up for
a service that runs for four days.
"""

import time
from collections import defaultdict, deque
from threading import Lock

# (calls, seconds). Ordered longest prefix first — the first match wins, so a
# more specific path has to appear before the prefix that contains it.
LIMITS: list[tuple[str, int, float]] = [
    ("/visits/claim", 5, 60.0),
    ("/world/verify", 10, 60.0),
    ("/qr/sign", 30, 60.0),
]
DEFAULT = (120, 60.0)

# Nothing here is worth remembering for long, and an unbounded dict keyed by IP
# is a slow leak in a service that stays up.
_SWEEP_EVERY = 300.0

_lock = Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_last_sweep = time.monotonic()


def reset() -> None:
    with _lock:
        _hits.clear()


def client_key(forwarded_for: str | None, peer: str | None) -> str:
    """Who is calling, as far as the proxy in front lets us see.

    Behind Render every connection arrives from Render's own proxy, so the peer
    address is the same for everybody, and a limit keyed on it is one limit for
    the whole world — a few people browsing at once would all get 429s. Render
    puts the real client first in X-Forwarded-For, so that is the key; the peer
    is the fallback for running with no proxy at all.

    A client can forge the header. What that buys is a way around a limit, not
    around a payment: a claim without a merchant's signature dies at gas
    estimation and never spends anything.
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"


def limit_for(path: str) -> tuple[int, float]:
    for prefix, calls, window in LIMITS:
        if path.startswith(prefix):
            return calls, window
    return DEFAULT


def _sweep(now: float) -> None:
    """Drop buckets nobody has touched for a while. Called under the lock."""
    global _last_sweep
    if now - _last_sweep < _SWEEP_EVERY:
        return
    _last_sweep = now
    stale = [key for key, seen in _hits.items() if not seen or now - seen[-1] > 3600]
    for key in stale:
        del _hits[key]


def check(client: str, path: str) -> float | None:
    """None if the call is allowed, or the seconds to wait if it is not.

    A sliding window rather than a fixed one: a fixed window lets somebody spend
    a whole minute's allowance at 11:59:59 and another at 12:00:00, which on the
    claim route is twice the gas we meant to allow.
    """
    calls, window = limit_for(path)
    now = time.monotonic()

    with _lock:
        _sweep(now)
        seen = _hits[(client, _bucket(path))]
        while seen and now - seen[0] >= window:
            seen.popleft()

        if len(seen) >= calls:
            return round(window - (now - seen[0]), 1)

        seen.append(now)
        return None


def _bucket(path: str) -> str:
    """Which allowance this path draws from.

    Per route rather than per URL, so `/campaigns/1` and `/campaigns/2` share
    one budget — otherwise a caller walking ids would never hit a limit.
    """
    for prefix, _, _ in LIMITS:
        if path.startswith(prefix):
            return prefix
    return "*"
