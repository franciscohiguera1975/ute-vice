"""Filas por facultad y estado de lote/proceso.

El SQL agrupa y filtra sobre un campo de texto libre, sin un conjunto de
valores fijo: se prueba contra PostgreSQL real y no con un doble en memoria,
que no ejecuta agrupamientos ni filtros SQL de verdad.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _sesion(settings):  # type: ignore[no-untyped-def]
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.infrastructure.db.sesion import crear_motor

    motor = crear_motor(settings.db)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    return motor, fabrica


async def _base(sesion):  # type: ignore[no-untyped-def]
    """Un pao, una carrera y una facultad, para las pruebas de flujo."""
    from app.infrastructure.db.modelos_distributivo import CarreraModel, FacultadModel, PaoModel

    pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
    carrera = CarreraModel(codigo="UIO:A - GRADO", nombre="UIO:A - GRADO")
    facultad = FacultadModel(codigo="FCII", nombre="FCII")
    sesion.add_all([pao, carrera, facultad])
    await sesion.flush()
    return pao, carrera, facultad


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
                # Satisface por defecto el filtro del flujo normal: estas
                # pruebas verifican el agrupamiento, no el filtro de flujo,
                # que tiene su propia clase de pruebas mas abajo.
                fase="Planificación",
            )
        )
    await sesion.commit()
    return pao


async def _fila_de_flujo(  # type: ignore[no-untyped-def]
    sesion,
    pao,
    carrera,
    facultad,
    *,
    estado="Aprobado",
    medida=None,
    generacion_contrato=None,
    fase="Planificación",
):
    """Una fila con control total sobre las tres columnas que deciden el
    flujo, para las pruebas de `_condicion_flujo`."""
    from app.infrastructure.db.modelos_distributivo import DocenteModel, FilaDistributivoModel

    docente = DocenteModel(
        identificacion=f"17{uuid.uuid4().int % 10**8:08d}", nombre_completo="Docente de prueba"
    )
    sesion.add(docente)
    await sesion.flush()
    sesion.add(
        FilaDistributivoModel(
            docente_id=docente.id,
            pao_id=pao.id,
            facultad_id=facultad.id,
            carrera_id=carrera.id,
            estado_lote=estado,
            medida=medida,
            generacion_contrato=generacion_contrato,
            fase=fase,
        )
    )


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


class TestFiltroDeFlujo:
    """Los tres flujos comparten la columna `estado_lote`, pero se distinguen
    por `medida`, `generación de contrato` y `fase`. Acordado con la
    institucion — ver `_condicion_flujo`."""

    async def test_contratacion_solo_exige_generacion_de_contrato(  # type: ignore[no-untyped-def]
        self, esquema: None
    ) -> None:
        from app.core.config import get_settings
        from app.domain.enums import TipoFlujoContrato
        from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

        motor, fabrica = await _sesion(get_settings())
        try:
            async with fabrica() as sesion:
                pao, carrera, facultad = await _base(sesion)
                # Genera contrato: cuenta, sin importar medida ni fase.
                await _fila_de_flujo(
                    sesion, pao, carrera, facultad, generacion_contrato="Si", fase="Ejecución"
                )
                # No genera contrato: no cuenta para este flujo.
                await _fila_de_flujo(sesion, pao, carrera, facultad, generacion_contrato=None)
                await sesion.commit()

                repo = RepositorioAnaliticaDistributivoSQL(sesion)
                resultado = await repo.estado_lote_por_facultad(
                    [pao.id], tipo_flujo=TipoFlujoContrato.CONTRATACION
                )

                assert resultado.por_facultad[0].total == 1
        finally:
            await motor.dispose()

    async def test_normal_excluye_las_medidas_con_tramite_propio(  # type: ignore[no-untyped-def]
        self, esquema: None
    ) -> None:
        from app.core.config import get_settings
        from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

        motor, fabrica = await _sesion(get_settings())
        try:
            async with fabrica() as sesion:
                pao, carrera, facultad = await _base(sesion)
                await _fila_de_flujo(sesion, pao, carrera, facultad, medida=None)
                # Tal como lo escribe hoy el origen, sin acento.
                await _fila_de_flujo(sesion, pao, carrera, facultad, medida="RENOVACION")
                # Como lo escribiria con acento, o "CAMBIO DE DEDICACIÓN".
                await _fila_de_flujo(sesion, pao, carrera, facultad, medida="Cambio de Dedicación")
                await _fila_de_flujo(sesion, pao, carrera, facultad, medida="NUEVA CONTRATACION")
                await sesion.commit()

                repo = RepositorioAnaliticaDistributivoSQL(sesion)
                resultado = await repo.estado_lote_por_facultad([pao.id])

                # Solo la fila sin medida-con-tramite-propio queda.
                assert resultado.por_facultad[0].total == 1
        finally:
            await motor.dispose()

    async def test_normal_exige_fase_planificacion(self, esquema: None) -> None:  # type: ignore[no-untyped-def]
        from app.core.config import get_settings
        from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

        motor, fabrica = await _sesion(get_settings())
        try:
            async with fabrica() as sesion:
                pao, carrera, facultad = await _base(sesion)
                await _fila_de_flujo(sesion, pao, carrera, facultad, fase="Planificación")
                await _fila_de_flujo(sesion, pao, carrera, facultad, fase="Ejecución")
                await _fila_de_flujo(sesion, pao, carrera, facultad, fase=None)
                await sesion.commit()

                repo = RepositorioAnaliticaDistributivoSQL(sesion)
                resultado = await repo.estado_lote_por_facultad([pao.id])

                assert resultado.por_facultad[0].total == 1
        finally:
            await motor.dispose()

    async def test_simplificado_exige_fase_ejecucion(self, esquema: None) -> None:  # type: ignore[no-untyped-def]
        from app.core.config import get_settings
        from app.domain.enums import TipoFlujoContrato
        from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

        motor, fabrica = await _sesion(get_settings())
        try:
            async with fabrica() as sesion:
                pao, carrera, facultad = await _base(sesion)
                await _fila_de_flujo(sesion, pao, carrera, facultad, fase="Ejecución")
                await _fila_de_flujo(sesion, pao, carrera, facultad, fase="Planificación")
                await sesion.commit()

                repo = RepositorioAnaliticaDistributivoSQL(sesion)
                resultado = await repo.estado_lote_por_facultad(
                    [pao.id], tipo_flujo=TipoFlujoContrato.SIMPLIFICADO
                )

                assert resultado.por_facultad[0].total == 1
        finally:
            await motor.dispose()

    async def test_el_orden_de_la_tabla_sigue_el_flujo_elegido(  # type: ignore[no-untyped-def]
        self, esquema: None
    ) -> None:
        from app.core.config import get_settings
        from app.domain.enums import TipoFlujoContrato
        from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL

        motor, fabrica = await _sesion(get_settings())
        try:
            async with fabrica() as sesion:
                pao, carrera, facultad = await _base(sesion)
                # Llegan en el orden inverso al del flujo simplificado. En
                # mayusculas: es como queda `estado_lote` una vez importado
                # por `FilaDistributivo.__post_init__`, y es contra eso que
                # compara `TipoFlujoContrato.orden_estados`.
                await _fila_de_flujo(
                    sesion, pao, carrera, facultad, estado="RECHAZADO", fase="Ejecución"
                )
                await _fila_de_flujo(
                    sesion, pao, carrera, facultad, estado="APROBADO", fase="Ejecución"
                )
                await _fila_de_flujo(
                    sesion,
                    pao,
                    carrera,
                    facultad,
                    estado="EN REVISIÓN POR DECANO",
                    fase="Ejecución",
                )
                await sesion.commit()

                repo = RepositorioAnaliticaDistributivoSQL(sesion)
                resultado = await repo.estado_lote_por_facultad(
                    [pao.id], tipo_flujo=TipoFlujoContrato.SIMPLIFICADO
                )

                assert resultado.estados == (
                    "EN REVISIÓN POR DECANO",
                    "APROBADO",
                    "RECHAZADO",
                )
        finally:
            await motor.dispose()
