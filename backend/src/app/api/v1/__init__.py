"""Agregacion de los routers de la version 1 de la API."""

from fastapi import APIRouter

from app.api.v1.routers import (
    autenticacion,
    catalogos,
    consultas,
    distributivo,
    personas,
    reportes,
    tablero,
    titulos,
    usuarios,
)

router_v1 = APIRouter()

router_v1.include_router(autenticacion.router)
router_v1.include_router(personas.router)
router_v1.include_router(titulos.router)
router_v1.include_router(consultas.router)
router_v1.include_router(tablero.router)
router_v1.include_router(reportes.router)
router_v1.include_router(catalogos.router)
router_v1.include_router(distributivo.router)
router_v1.include_router(usuarios.router)

__all__ = ["router_v1"]
