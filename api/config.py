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

    # How long a batch of fraud scores stays open before its root is committed.
    # An hour is short enough that a held reward is resolved the same afternoon,
    # and long enough that we are not paying gas every few minutes. Changing it
    # renumbers every past epoch, so it moves with the contract or not at all.
    epoch_seconds: int = 3600

    # The QR on the merchant screen redraws every 30 seconds, but a signature
    # stays valid for 90. The gap is deliberate: a slow scan on a bad phone
    # should not fail, and a photographed QR is still dead a minute later.
    qr_rotation_seconds: int = 30
    signature_ttl_seconds: int = 90

    # --- World -------------------------------------------------------------
    #
    # Selfie Check cannot be verified on chain. The World ID Router only takes
    # Orb credentials — `groupId` must be 1 — and the v4 verifier lives on World
    # Chain, not Base. So the contract cannot ask World anything, and the only
    # path is: our backend asks World, and then vouches for the answer.
    #
    # That vouching is a signature, and it costs something honest to say out
    # loud: the contract trusts us on this one fact. Everywhere else in ZoneGo
    # the merchant signs and the chain verifies, and we hold no authority. Here
    # we do. It is World's protocol that forces it, and the video says so rather
    # than hiding it.
    world_app_id: str = ""
    world_rp_id: str = ""
    # Signs the requests we send World, proving they came from ZoneGo. Their
    # documentation is blunt about it: never expose this to client-side code.
    world_rp_signing_key: str = ""
    # Scopes what a person is proving. An arbitrary string, not something
    # registered in the portal — but it has to match on all three sides.
    world_action: str = "verify-visitor"
    world_api_url: str = "https://developer.world.org/api/v4/verify"
    world_timeout_seconds: float = 15.0

    # Signs the attestation the contract verifies. A different key from the
    # relay on purpose: leaking the relay costs gas, leaking this one lets
    # somebody mint verified humans and drain a campaign.
    attester_private_key: str = ""
    # An attestation is carried to the contract by the same person it names, in
    # the same session. Two minutes is long enough for a slow phone and short
    # enough that one intercepted off a screen is already dead.
    attestation_ttl_seconds: int = 120

    # --- Epoch publication -------------------------------------------------
    #
    # A third key, and again not a spare copy of the others. Leaking the relay
    # costs gas; leaking the attester lets somebody mint verified humans;
    # leaking this one lets somebody rewrite who the model called fraudulent.
    # Three consequences, three keys.
    #
    # It sends one transaction an hour, so it needs a fraction of the relay's
    # balance. Empty until Sebastián redeploys with the address of the oracle —
    # the job runs the whole path either way and says which of the two is
    # missing rather than failing silently every hour.
    fraud_oracle_address: str = "0x0000000000000000000000000000000000000000"
    fraud_operator_private_key: str = ""


@lru_cache
def get_config() -> Config:
    return Config()


def cors_origin_list() -> list[str]:
    return [o.strip() for o in get_config().cors_origins.split(",") if o.strip()]
