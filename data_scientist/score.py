import os
import sys

import requests
from fastapi import APIRouter, HTTPException

# FIX: this used to be a try/except that imported from "infer" in BOTH
# branches — a no-op fallback that silently defeated its own purpose (if
# the first import ever failed, the except failed the exact same way).
#
# The deeper issue restoring "from ml.infer import ..." doesn't actually
# fix: infer.py (and everything it imports — events.py, features.py,
# graph_features.py) uses FLAT sibling imports ("from events import ...",
# not "from .events import ..."). That only resolves if the ml/ directory
# itself is on sys.path. Importing "ml" as a package from further up the
# repo (`from ml.infer import ...`) gets past the first import fine, then
# breaks one line into infer.py with "No module named 'events'" — tested
# this directly, it reproduces every time. Converting every cross-import
# inside ml/*.py to package-relative imports would fix it too, but touches
# four files instead of one and changes how `python3 train.py` is run.
#
# This puts ml/ on sys.path first, THEN does the same flat import infer.py
# itself uses — no changes needed to any file inside ml/.
# ZONEGO_ML_DIR overrides the guess if ml/ lives somewhere else in your
# real repo layout; otherwise a couple of common relative layouts are
# tried automatically.
_ML_DIR = os.environ.get("ZONEGO_ML_DIR")
if not _ML_DIR:
    _here = os.path.dirname(os.path.abspath(__file__))
    for _candidate in ("../../ml", "../ml", "./ml", "."):
        _resolved = os.path.normpath(os.path.join(_here, _candidate))
        if os.path.isfile(os.path.join(_resolved, "infer.py")):
            _ML_DIR = _resolved
            break

if _ML_DIR and _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)

from infer import score_wallet, load_bundle, get_operating_threshold  # noqa: E402

router = APIRouter(prefix="/score", tags=["score"])

# Adjust this to match how the subgraph URL is resolved 
# elsewhere in the API (environment variable, config, etc.)
# — this value is simply the one documented in events.py as the deployed subgraph.
SUBGRAPH_URL = os.environ.get(
    "ZONEGO_SUBGRAPH_URL",
    "https://api.studio.thegraph.com/query/1758817/zone-go/v0.0.1",
)

# The bundle (model + fitted features + threshold) is loaded once upon
# importing the router, not on every request—score_wallet() receives the
# bundle directly to avoid re-reading the .joblib file on each call.
_bundle = None


def _get_bundle():
    global _bundle
    if _bundle is None:
        _bundle = load_bundle()
    return _bundle


@router.get("/{wallet}")
def wallet_score(wallet: str) -> float:
    """Returns the wallet's fraud_score as a float in [0, 1] — and nothing
    else. It does not decide retention, it does not convert to basis points, it does not touch the
    payment tree: that is the responsibility of whoever calls this endpoint
    (the payment tree code), not this router.

    FIX (Observations #3 + #4, closed via ml/infer.py::score_wallet()):
    previously returned 501 because load_events_from_subgraph() was not
    connected to any actual caller.
    """
    try:
        bundle = _get_bundle()
    except FileNotFoundError as exc:
        # The model has not been trained yet (fraud_model.joblib does not exist).
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        score = score_wallet(wallet, SUBGRAPH_URL, bundle=bundle)
    except requests.exceptions.RequestException as exc:
        # The subgraph did not respond — this is an external service issue,
        # not an issue with this wallet or this endpoint. 502, not 500.
        raise HTTPException(status_code=502, detail=f"Subgraph unreachable: {exc}")
    except RuntimeError as exc:
        # events.load_events_from_subgraph() raises RuntimeError when the
        # subgraph responds but with GraphQL errors.
        raise HTTPException(status_code=502, detail=f"Subgraph query failed: {exc}")

    if score is None:
        raise HTTPException(status_code=404, detail=f"No indexed visits found for {wallet}")

    # TODO(Lucio / whoever owns the payment tree): this is where `score`
    # (float 0..1) is converted to basis points and inserted into the tree.
    # That code was not among the files provided to me, so I cannot
    # write it for you without guessing its shape — but the integration point
    # is exactly this return value.
    return score


@router.get("/{wallet}/threshold")
def wallet_score_threshold(point: str = "high_recall_point") -> float:
    """Auxiliary endpoint, NOT part of the original contract: exposes the threshold
    calculated by train.py using the precision-recall curve (see README.md,
    "Operating threshold" section), so the payment tree doesn't have to
    hardcode that number. `point` is either "f1_point" or "high_recall_point".
    Delete this if the payment tree already reads the .joblib directly.
    """
    try:
        bundle = _get_bundle()
        return get_operating_threshold(bundle=bundle, point=point)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))



