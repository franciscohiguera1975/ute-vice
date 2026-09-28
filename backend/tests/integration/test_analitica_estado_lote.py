"""Filas por facultad y estado de lote/proceso.

El SQL agrupa y filtra sobre un campo de texto libre, sin un conjunto de
valores fijo: se prueba contra PostgreSQL real y no con un doble en memoria,
que no ejecuta agrupamientos ni filtros SQL de verdad.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _sesion(settings):  # type: ignore[no-untyped-def]
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.infrastructure.db.sesion import crear_motor

    motor = crear_motor(settings.db)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    return motor, fabrica


async def _preparar(sesion, filas_estado):  # type: ignore[no-untyped-def]
    """Crea un pao, una facultad por letra y una fila por (facultad, estado).

    `filas_estado` es una lista de `(letra_facultad, estado_o_None)`.
    """
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
    )

    pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
    carrera = CarreraModel(codigo="UIO:A - GRADO", nombre="UIO:A - GRADO")
    sesion.add_all([pao, carrera])
    await sesion.flush()

    facultades = {}
    for letra, _ in filas_estado:
        if letra not in facultades:
            facultades[letra] = FacultadModel(codigo=letra, nombre=f"Facultad {letra}")
            sesion.add(facultades[letra])
    await sesion.flush()

    for numero, (letra, estado) in enumerate(filas_estado):
        docente = DocenteModel(identificacion=f"171003{numero:04d}", nombre_completo=f"D{numero}")
        sesion.add(docente)
        await sesion.flush()
        sesion.add(
            FilaDistributivoModel(
                docente_id=docente.id,
                pao_id=pao.id,
                facultad_id=facultades[letra].id,
                carrera_id=carrera.id,
                estado_lote=estado,
            )
        )
    await sesion.commit()
    return pao


async def test_solo_cuenta_filas_con_estado_de_lote(esquema: None) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = await _preparar(
                sesion,
                [
                    ("FCII", "Aprobado"),
                    ("FCII", "Rechazado"),
                    ("FCII", None),  # sin estado: no cuenta
                    ("FAU", "Aprobado"),
                ],
            )

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            resultado = await repo.estado_lote_por_facultad([pao.id])

            assert set(resultado.estados) == {"Aprobado", "Rechazado"}
            por_codigo = {f.codigo: f for f in resultado.por_facultad}
            assert por_codigo["FCII"].conteos == {"Aprobado": 1, "Rechazado": 1}
            assert por_codigo["FCII"].total == 2
            assert por_codigo["FAU"].conteos == {"Aprobado": 1}
    finally:
        await motor.dispose()


async def test_filtrar_por_estados_no_borra_las_opciones_disponibles(  # type: ignore[no-untyped-def]
    esquema: None,
) -> None:
    """`estados` acota la tabla, pero no la lista de casillas ofrecidas."""
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = await _preparar(
                sesion,
                [
                    ("FCII", "Aprobado"),
                    ("FCII", "Rechazado"),
                    ("FAU", "En revisión por DGA"),
                ],
            )

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            resultado = await repo.estado_lote_por_facultad([pao.id], estados=["Aprobado"])

            # Las tres opciones siguen disponibles para volver a marcarlas...
            assert set(resultado.estados) == {"Aprobado", "Rechazado", "En revisión por DGA"}
            # ...pero la tabla solo trae lo que se pidio.
            por_codigo = {f.codigo: f for f in resultado.por_facultad}
            assert por_codigo["FCII"].conteos == {"Aprobado": 1}
            assert "FAU" not in por_codigo
    finally:
        await motor.dispose()


async def test_sin_filas_con_estado_devuelve_vacio(esquema: None) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = await _preparar(sesion, [("FCII", None)])

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            resultado = await repo.estado_lote_por_facultad([pao.id])

            assert resultado.estados == ()
            assert resultado.por_facultad == []
    finally:
        await motor.dispose()
