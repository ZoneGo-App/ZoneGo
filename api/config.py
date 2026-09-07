from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    mock_mode: bool = True
    rpc_url: str = ""
    subgraph_url: str = ""
    fraud_threshold: float = 0.72

    # Base Sepolia: the one testnet all three sponsors support.
    chain_id: int = 84532
    visit_registry_address: str = "0x0000000000000000000000000000000000000000"

    # The QR on the merchant screen redraws every 30 seconds, but a signature
    # stays valid for 90. The gap is deliberate: a slow scan on a bad phone
    # should not fail, and a photographed QR is still dead a minute later.
    qr_rotation_seconds: int = 30
    signature_ttl_seconds: int = 90


@lru_cache
def get_config() -> Config:
    return Config()
