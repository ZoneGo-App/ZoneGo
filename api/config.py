from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # Read from a .env in the working directory, so running uvicorn by hand
    # picks up the same values docker compose already substitutes. Real
    # environment variables still win, which is what a deployment sets.
    # `extra="ignore"` because that file is shared with compose and holds keys
    # this class has never heard of.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mock_mode: bool = True
    rpc_url: str = ""
    subgraph_url: str = ""
    fraud_threshold: float = 0.72

    # Seconds a subgraph answer is reused. Search and the merchant panel ask
    # for the same campaigns within the same second.
    subgraph_cache_seconds: float = 5.0
    subgraph_timeout_seconds: float = 8.0

    # Comma separated. The deployed frontend lives on its own domain, so this
    # has to be set in production or the browser blocks every request.
    cors_origins: str = "http://localhost:3000"

    # Base Sepolia: the one testnet all three sponsors support.
    chain_id: int = 84532
    visit_registry_address: str = "0x0000000000000000000000000000000000000000"
    campaign_vault_address: str = "0x0000000000000000000000000000000000000000"

    # A node read is one round trip to an RPC provider, so the same campaign
    # asked for twice in a second costs twice. Shorter than the subgraph's
    # window because this is the path used when freshness is the point.
    rpc_cache_seconds: float = 2.0
    rpc_timeout_seconds: float = 8.0

    # Pays the gas so a visitor with an empty wallet can still claim. It signs
    # transactions, never visits — the merchant's signature is what the contract
    # verifies. Keep it funded with testnet ETH and out of the repository.
    relay_private_key: str = ""

    # The QR on the merchant screen redraws every 30 seconds, but a signature
    # stays valid for 90. The gap is deliberate: a slow scan on a bad phone
    # should not fail, and a photographed QR is still dead a minute later.
    qr_rotation_seconds: int = 30
    signature_ttl_seconds: int = 90


@lru_cache
def get_config() -> Config:
    return Config()


def cors_origin_list() -> list[str]:
    return [o.strip() for o in get_config().cors_origins.split(",") if o.strip()]
