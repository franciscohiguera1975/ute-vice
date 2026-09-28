"""Que sumar horas por docente no duplique una carga que se exploto en varias
filas del distributivo.

Una fila del sistema academico que junta varias carreras, sedes o periodos a
la vez se guarda como varias filas —una por combinacion, todas con la misma
carga— que comparten `grupo_combinado_id`. Los dobles en memoria no generan
SQL, asi que esta comprobacion necesita PostgreSQL real: es la unica forma de
probar que la ventana `ROW_NUMBER() OVER (PARTITION BY ...)` de
`_suma_sin_duplicar` hace lo que dice.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


async def _sesion(settings):  # type: ignore[no-untyped-def]
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.infrastructure.db.sesion import crear_motor

    motor = crear_motor(settings.db)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    return motor, fabrica


async def test_grupo_combinado_no_duplica_las_horas(esquema: None) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
    )

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
            facultad = FacultadModel(codigo="FCII", nombre="FCII")
            carrera_a = CarreraModel(codigo="UIO:A - GRADO", nombre="UIO:A - GRADO")
            carrera_b = CarreraModel(codigo="UIO:B - GRADO", nombre="UIO:B - GRADO")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            sesion.add_all([pao, facultad, carrera_a, carrera_b, docente])
            await sesion.flush()

            # Una carga de 8h de Da que el origen junto en dos carreras a la
            # vez: dos filas del distributivo, mismo grupo_combinado_id.
            grupo = uuid4()
            for carrera in (carrera_a, carrera_b):
                sesion.add(
                    FilaDistributivoModel(
                        docente_id=docente.id,
                        pao_id=pao.id,
                        facultad_id=facultad.id,
                        carrera_id=carrera.id,
                        horas_docencia={"Da": 8.0},
                        total_docencia=8.0,
                        total_horas=8.0,
                        grupo_combinado_id=grupo,
                    )
                )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            totales = await repo.totales_por_dedicacion([pao.id])

            # Docente distinto: uno. Horas: 8, no 16 — es la misma carga.
            assert totales.docentes == 1
            assert totales.horas_da == 8.0

            # Pero por carrera si cuenta completa en cada una: es el reporte
            # que confirmo la institucion, no un descuido de este cambio.
            por_carrera = await repo.horas_por_carrera([pao.id])
            assert {(f.carrera, f.horas_da) for f in por_carrera} == {
                ("UIO:A - GRADO", 8.0),
                ("UIO:B - GRADO", 8.0),
            }
    finally:
        await motor.dispose()


async def test_sin_grupo_combinado_las_horas_se_suman_normal(esquema: None) -> None:  # type: ignore[no-untyped-def]
    """Dos docentes distintos, sin `grupo_combinado_id`: nada que deduplicar."""
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
    )

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
            facultad = FacultadModel(codigo="FCII", nombre="FCII")
            carrera = CarreraModel(codigo="UIO:A - GRADO", nombre="UIO:A - GRADO")
            docente_1 = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            docente_2 = DocenteModel(identificacion="0926687856", nombre_completo="RUIZ ANA")
            sesion.add_all([pao, facultad, carrera, docente_1, docente_2])
            await sesion.flush()

            for docente in (docente_1, docente_2):
                sesion.add(
                    FilaDistributivoModel(
                        docente_id=docente.id,
                        pao_id=pao.id,
                        facultad_id=facultad.id,
                        carrera_id=carrera.id,
                        horas_docencia={"Da": 8.0},
                        total_docencia=8.0,
                        total_horas=8.0,
                    )
                )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            totales = await repo.totales_por_dedicacion([pao.id])

            assert totales.docentes == 2
            assert totales.horas_da == 16.0
    finally:
        await motor.dispose()


async def test_grupo_combinado_no_duplica_en_validacion_de_grupo(esquema: None) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
    )

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            # Grado y posgrado del mismo semestre: la carga combinada cuenta
            # para los dos, y `validacion_de_grupo` los mira juntos.
            pao_grado = PaoModel(codigo="262651", nombre="2026-2 GRADO")
            pao_posgrado = PaoModel(codigo="262751", nombre="2026-2 POSGRADO")
            facultad = FacultadModel(codigo="FCII", nombre="FCII")
            carrera = CarreraModel(codigo="UIO:A - GRADO", nombre="UIO:A - GRADO")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            sesion.add_all([pao_grado, pao_posgrado, facultad, carrera, docente])
            await sesion.flush()

            grupo = uuid4()
            for pao in (pao_grado, pao_posgrado):
                sesion.add(
                    FilaDistributivoModel(
                        docente_id=docente.id,
                        pao_id=pao.id,
                        facultad_id=facultad.id,
                        carrera_id=carrera.id,
                        horas_docencia={"Da": 10.0},
                        total_docencia=10.0,
                        total_horas=10.0,
                        grupo_combinado_id=grupo,
                    )
                )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            validacion = await repo.validacion_de_grupo([pao_grado.id, pao_posgrado.id])

            assert validacion is not None
            # Dos filas —una por periodo, la cuenta que le interesa a quien
            # valida—, un solo docente, y las horas sin duplicar.
            assert validacion.total == 2
            assert validacion.docentes == 1
            assert validacion.horas == 10.0
    finally:
        await motor.dispose()
