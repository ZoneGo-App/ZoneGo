from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    mock_mode: bool = True
    rpc_url: str = ""
    subgraph_url: str = ""
    fraud_threshold: float = 0.72


@lru_cache
def get_config() -> Config:
    return Config()
