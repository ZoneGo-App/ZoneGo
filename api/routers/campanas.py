from fastapi import APIRouter, HTTPException

from api.config import obtener_config
from api.esquema import Campana
from api.simulador import CAMPANAS

router = APIRouter(prefix="/campanas", tags=["campanas"])


@router.get("", response_model=list[Campana])
def listar_campanas():
    config = obtener_config()
    if config.modo_simulado:
        return CAMPANAS
    raise HTTPException(501, "Falta conectar el subgraph")


@router.get("/{id_campana}", response_model=Campana)
def obtener_campana(id_campana: int):
    config = obtener_config()
    if config.modo_simulado:
        for c in CAMPANAS:
            if c.id_campana == id_campana:
                return c
        raise HTTPException(404, "Campana no encontrada")
    raise HTTPException(501, "Falta conectar el subgraph")
