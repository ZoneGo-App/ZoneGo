from datetime import datetime, timedelta, timezone

from api.esquema import Campana

AHORA = datetime.now(timezone.utc)

CAMPANAS = [
    Campana(
        id_campana=1,
        comercio="0x1F6BFD8F9242aC5eEf6b21082a9C460907e39e03",
        nombre_comercio="Panaderia San Jose",
        rubro="panaderia",
        recompensa_por_visita=250000,
        tope_diario=40,
        geohash="6mc5rvw2",
        radio_metros=120,
        saldo=48500000,
        creada=AHORA - timedelta(days=2),
    ),
    Campana(
        id_campana=2,
        comercio="0x9aB4c3D2e1F0a9B8c7D6e5F4a3B2c1D0e9F8a7B6",
        nombre_comercio="Bodega Dona Rosa",
        rubro="bodega",
        recompensa_por_visita=150000,
        tope_diario=60,
        geohash="6mc5rvx7",
        radio_metros=80,
        saldo=22000000,
        creada=AHORA - timedelta(days=1),
    ),
    Campana(
        id_campana=3,
        comercio="0x3C2b1A0f9E8d7C6b5A4f3E2d1C0b9A8f7E6d5C4b",
        nombre_comercio="Menu Criollo El Rincon",
        rubro="restaurante",
        recompensa_por_visita=400000,
        tope_diario=25,
        geohash="6mc5rvz1",
        radio_metros=150,
        saldo=9800000,
        creada=AHORA - timedelta(hours=20),
    ),
]
