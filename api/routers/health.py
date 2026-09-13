"""Whether the service is up, and whether it can actually do its job.

Two different questions, and conflating them is how a deployment sits green for
a day while every claim fails. `/health` says the process answers. `/ready` says
the things it depends on are configured and reachable — a node, an index, the
keys it signs with.

An uptime check points at `/health`. A person debugging points at `/ready`.
"""

import httpx
from fastapi import APIRouter
from web3 import Web3
from web3.exceptions import Web3Exception

from api import observability
from api.config import get_config

router = APIRouter()

ZERO = "0x0000000000000000000000000000000000000000"


@router.get("/health")
def health():
    """Cheap and always true while the process is alive."""
    config = get_config()
    return {
        "status": "ok",
        "version": "0.1.0",
        "mock_mode": config.mock_mode,
    }


@router.get("/ready")
def ready():
    """What is wired up, and what would fail if somebody claimed right now.

    Mock mode answers everything from samples, so nothing external is required
    and saying otherwise would be a false alarm on a service that is working
    exactly as configured.
    """
    config = get_config()
    if config.mock_mode:
        return {"ready": True, "mock_mode": True, "checks": {}}

    checks = {
        "subgraph": _subgraph(config),
        "node": _node(config),
        "relay_key": "configured" if config.relay_private_key else "missing",
        "attester_key": "configured" if config.attester_private_key else "missing",
        "operator_key": (
            "configured" if config.fraud_operator_private_key else "missing"
        ),
        "world_rp": "configured" if config.world_rp_id else "missing",
        "vault_address": "set" if config.campaign_vault_address != ZERO else "unset",
        "registry_address": "set" if config.visit_registry_address != ZERO else "unset",
        "oracle_address": "set" if config.fraud_oracle_address != ZERO else "unset",
    }

    # A missing key is not an outage — the API still reads and still signs QR
    # payloads. What makes it not ready is being unable to answer at all.
    ready_now = checks["subgraph"] == "ok" and checks["node"] == "ok"
    return {"ready": ready_now, "mock_mode": False, "checks": checks}


@router.get("/metrics")
def metrics():
    """Counters since the process started.

    Deliberately small and human-readable rather than Prometheus text: what a
    person wants to know at 3am is how many claims were rejected and why, and
    that fits in a page.
    """
    return observability.snapshot()


def _subgraph(config) -> str:
    if not config.subgraph_url:
        return "missing"
    try:
        r = httpx.post(
            config.subgraph_url,
            json={"query": "{ _meta { block { number } } }"},
            timeout=config.subgraph_timeout_seconds,
        )
        return "ok" if r.status_code < 400 else f"http {r.status_code}"
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        # InvalidURL means the setting is malformed rather than the service
        # being down. /ready exists to say which, so it must not be the one
        # endpoint that dies of it.
        return f"unreachable: {type(exc).__name__}"


def _node(config) -> str:
    if not config.rpc_url:
        return "missing"
    try:
        w3 = Web3(
            Web3.HTTPProvider(
                config.rpc_url, request_kwargs={"timeout": config.rpc_timeout_seconds}
            )
        )
        return "ok" if w3.eth.chain_id == config.chain_id else "wrong chain"
    except (Web3Exception, OSError) as exc:
        return f"unreachable: {type(exc).__name__}"
