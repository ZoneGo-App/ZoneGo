from datetime import datetime

from pydantic import BaseModel, Field


class Campana(BaseModel):
    id_campana: int = Field(..., ge=0)
    comercio: str
    nombre_comercio: str = Field(..., min_length=1, max_length=120)
    rubro: str
    recompensa_por_visita: int = Field(..., gt=0)
    tope_diario: int = Field(..., gt=0)
    geohash: str
    radio_metros: int = Field(..., gt=0, le=2000)
    saldo: int = Field(..., ge=0)
    activa: bool = True
    creada: datetime
