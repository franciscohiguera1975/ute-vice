"""Endpoints del tablero de indicadores."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencias import ContenedorDep, ContextoDep, requiere
from app.api.esquemas.nucleo import TableroSalida
from app.application.casos_uso.analitica import EntradaTablero, ObtenerTablero
from app.domain.enums import Permiso

router = APIRouter(prefix="/tablero", tags=["Tablero"])


@router.get(
    "",
    response_model=TableroSalida,
    summary="Indicadores del tablero",
    dependencies=[requiere(Permiso.DASHBOARD_VER)],
)
async def tablero(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    dias: Annotated[int, Query(ge=1, le=365, description="Ventana de analisis en dias")] = 30,
) -> TableroSalida:
    """Devuelve todos los indicadores en una sola llamada.

    Se agrupan a proposito: con seis peticiones concurrentes, los numeros
    podrian no ser coherentes entre si al pintarlos en la misma pantalla.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica(uow.sesion)  # type: ignore[attr-defined]
        caso = ObtenerTablero(analitica, contenedor.reloj)
        resultado = await caso(EntradaTablero(dias=dias), contexto)
    return TableroSalida.desde(resultado)
