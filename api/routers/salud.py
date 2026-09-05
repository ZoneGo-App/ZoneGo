from fastapi import APIRouter

from api.config import obtener_config

router = APIRouter()


@router.get("/salud")
def salud():
    config = obtener_config()
    return {
        "estado": "ok",
        "version": "0.1.0",
        "modo_simulado": config.modo_simulado,
    }
