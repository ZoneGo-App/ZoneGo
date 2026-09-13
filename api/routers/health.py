"""Whether the service is up, and whether it can actually do its job.

Two different questions, and conflating them is how a deployment sits green for
a day while every claim fails. `/health` says the process answers. `/ready` says
the things it depends on are configured and reachable — a node, an index, the
keys it signs with.

An uptime check points at `/health`. A person debugging points at `/ready`.
"""

import httpx
from eth_account import Account
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
        "relay_key": _key(config.relay_private_key),
        "attester_key": _key(config.attester_private_key),
        "operator_key": _key(config.fraud_operator_private_key),
        "world_rp": "configured" if config.world_rp_id else "missing",
        "vault_address": _address(config.campaign_vault_address),
        "registry_address": _address(config.visit_registry_address),
        "oracle_address": _address(config.fraud_oracle_address),
    }

    # A missing key is not an outage — the API still reads and still signs QR
    # payloads. What makes it not ready is being unable to answer at all.
    ready_now = checks["subgraph"] == "ok" and checks["node"] == "ok"
    return {"ready": ready_now, "mock_mode": False, "checks": checks}


def _key(value: str) -> str:
    """Whether a private key is there, and whether it is one.

    "configured" used to mean only "not empty". A relay key that reached the
    host malformed read as configured here while every claim failed with a 500,
    which is the exact case this endpoint exists to catch. Parsing it costs
    nothing and says nothing about the key beyond whether it parses.
    """
    if not value:
        return "missing"
    try:
        Account.from_key(value)
    except Exception:  # noqa: BLE001 — any parse failure is the same answer
        return "invalid"
    return "configured"


def _address(value: str) -> str:
    if value == ZERO:
        return "unset"
    return "set" if Web3.is_address(value) else "invalid"


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
