from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    modo_simulado: bool = True
    rpc_url: str = ""
    url_subgraph: str = ""
    umbral_fraude: float = 0.72


@lru_cache
def obtener_config() -> Config:
    return Config()