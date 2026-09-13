import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import epoch_job, observability, ratelimit
from api.config import cors_origin_list, get_config
from api.routers import (
    campaigns,
    epochs,
    health,
    leaderboard,
    qr,
    score,
    search,
    visits,
    world,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Say it out loud on boot. A deployment left in mock mode answers 200 to
    everything and looks perfectly healthy while serving invented data."""
    observability.configure_logging()
    config = get_config()
    log = logging.getLogger("uvicorn.error")
    if config.mock_mode:
        log.warning("ZoneGo API up in MOCK MODE — responses are sample data")
    else:
        log.info("ZoneGo API up in live mode, chain %s", config.chain_id)
    log.info("CORS allows: %s", ", ".join(cors_origin_list()))

    # Only in live mode: in mock mode the epoch would be built from sample
    # wallets, which is a root over invented data — worse than no root at all,
    # because it looks real in a log.
    job = None
    if not config.mock_mode:
        job = asyncio.create_task(epoch_job.loop())

    yield

    if job is not None:
        job.cancel()


app = FastAPI(
    title="ZoneGo API",
    version="0.1.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def throttle_and_count(request: Request, call_next):
    """One caller's budget per route, and a tally of what came back.

    Ahead of the routes on purpose: a claim that is going to be refused should
    cost nothing, and the point of limiting that path is that reaching the relay
    at all spends gas.
    """
    # Health and metrics are what an uptime check and a person debugging use,
    # and throttling those means going blind exactly when it matters.
    if request.url.path not in ("/health", "/ready", "/metrics"):
        client = ratelimit.client_key(
            request.headers.get("x-forwarded-for"),
            request.client.host if request.client else None,
        )
        wait = ratelimit.check(client, request.url.path)
        if wait is not None:
            observability.rejected(
                "rate_limited", path=request.url.path, client=client, retry_after=wait
            )
            observability.record_response(429)
            return JSONResponse(
                {"detail": f"Too many requests. Try again in {wait}s."},
                status_code=429,
                headers={"Retry-After": str(int(wait) + 1)},
            )

    response = await call_next(request)
    observability.record_response(response.status_code)
    return response


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
app.include_router(leaderboard.router)
app.include_router(epochs.router)
app.include_router(world.router)
