"""What the service says about itself when nobody is watching it live.

A rejected claim is the interesting event in ZoneGo. Somebody walked to a shop,
scanned, and did not get paid — and the honest question afterwards is always the
same: was that the system working, or was that us? A line of prose in a log
cannot answer it. A record with the campaign, the reason and the time can.

So rejections are logged as JSON, one object per line, and counted in memory so
a deployment can be watched without shipping logs anywhere. Both are deliberately
small: no agent, no collector, no new dependency two days before a deadline.

The counters live in this process and reset when it restarts. That is a real
limit and it is the right trade here — the alternative is a metrics backend the
team would have to run, for a service that will be up for four days.
"""

import json
import logging
import time
from collections import Counter
from threading import Lock

log = logging.getLogger("zonego")


class JsonLines(logging.Formatter):
    """One JSON object per line, so `grep` and a log viewer both work.

    Anything passed through `extra=` lands beside the message rather than being
    formatted into it, which is the whole point: a reason you can filter on
    instead of a sentence you have to read.
    """

    KEEP = {"levelname", "name", "message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLines())
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    # Uvicorn already prints its own access lines; ours are the domain events,
    # so they travel separately rather than being swallowed by that logger.
    log.propagate = False


# --- counters ---------------------------------------------------------------

_lock = Lock()
_rejections: Counter[str] = Counter()
_responses: Counter[str] = Counter()
_started_at = time.time()


def reset_counters() -> None:
    with _lock:
        _rejections.clear()
        _responses.clear()


def record_response(status_code: int) -> None:
    with _lock:
        _responses[f"{status_code // 100}xx"] += 1


def rejected(reason: str, **fields) -> None:
    """A claim that did not become a payment, and why.

    `reason` is a short stable slug rather than a sentence, because it is the
    thing you group by when a merchant asks why nobody got paid this afternoon.
    """
    with _lock:
        _rejections[reason] += 1
    log.warning("claim_rejected", extra={"reason": reason, **fields})


def snapshot() -> dict:
    with _lock:
        return {
            "uptime_seconds": round(time.time() - _started_at),
            "responses": dict(_responses),
            "rejected_claims": dict(_rejections),
            "rejected_total": sum(_rejections.values()),
        }
