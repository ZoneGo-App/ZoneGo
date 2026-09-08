"""Test settings, pinned so the suite never reads anybody's .env.

`Config` loads a .env so a developer can run the API against Base Sepolia
without exporting six variables. That file then follows pytest into every test
process, and a suite whose result depends on whether someone has filled in
their own RPC URL is not a suite — it goes green on one machine and red in CI
for reasons nobody can see in the diff.

So every test starts from the same place: mock mode, no node, no index, no key.
Tests that want live mode say so themselves, and their monkeypatching runs
after this and wins.
"""

import pytest

from api import chain, epochs
from api.config import get_config

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch):
    config = get_config()
    monkeypatch.setattr(config, "mock_mode", True)
    monkeypatch.setattr(config, "rpc_url", "")
    monkeypatch.setattr(config, "subgraph_url", "")
    monkeypatch.setattr(config, "relay_private_key", "")
    monkeypatch.setattr(config, "campaign_vault_address", ZERO_ADDRESS)
    monkeypatch.setattr(config, "visit_registry_address", ZERO_ADDRESS)
    # Node reads are memoised across calls, so a campaign cached by one test
    # would answer in the next one. An epoch is cached the same way, and it is
    # worse: a root built under one test's wallets would be served to the next.
    chain.clear_cache()
    epochs.clear_cache()
    yield
    chain.clear_cache()
    epochs.clear_cache()
