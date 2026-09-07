import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import cors_origin_list, get_config
from api.routers import campaigns, health, qr, score, search, visits


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Say it out loud on boot. A deployment left in mock mode answers 200 to
    everything and looks perfectly healthy while serving invented data."""
    config = get_config()
    log = logging.getLogger("uvicorn.error")
    if config.mock_mode:
        log.warning("ZoneGo API up in MOCK MODE — responses are sample data")
    else:
        log.info("ZoneGo API up in live mode, chain %s", config.chain_id)
    log.info("CORS allows: %s", ", ".join(cors_origin_list()))
    yield


app = FastAPI(
    title="ZoneGo API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(campaigns.router)
app.include_router(search.router)
app.include_router(qr.router)
app.include_router(visits.router)
app.include_router(score.router)
