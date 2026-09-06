from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import campaigns, health

app = FastAPI(
    title="ZoneGo API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(campaigns.router)
