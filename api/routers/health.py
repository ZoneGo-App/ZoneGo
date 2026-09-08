from fastapi import APIRouter

from api.config import get_config

router = APIRouter()


@router.get("/health")
def health():
    config = get_config()
    return {
        "status": "ok",
        "version": "0.1.0",
        "mock_mode": config.mock_mode,
    }
