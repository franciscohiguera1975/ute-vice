"""`docentes_resumen` y `split_por_carrera`, las dos consultas del Tablero
Docente.

Igual que `test_analitica_distributivo_grupo_combinado.py`, necesitan
PostgreSQL real: la deduplicacion por `grupo_combinado_id` se hace con una
ventana `ROW_NUMBER() OVER (PARTITION BY ...)` que no tiene equivalente en
memoria.
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


async def test_docentes_resumen_suma_horas_y_usa_la_fila_de_mas_carga(
    esquema: None,
) -> None:  # type: ignore[no-untyped-def]
    """Un docente con dos carreras: las horas se suman entre ambas, y su
    facultad/categoria/dedicacion «principal» salen de la fila con mas horas
    totales — igual que `avance_por_facultad` elige la facultad de mas carga.
    """
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        CategoriaModel,
        DedicacionModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
        TitularidadModel,
    )

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
            fac_a = FacultadModel(codigo="FCII", nombre="Ingenieria e Industrias")
            fac_b = FacultadModel(codigo="FAU", nombre="Arquitectura y Urbanismo")
            carrera_a = CarreraModel(codigo="SISTEMAS", nombre="SISTEMAS")
            carrera_b = CarreraModel(codigo="ARQUITECTURA", nombre="ARQUITECTURA")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            titular = TitularidadModel(codigo="TITULAR", nombre="TITULAR")
            tc = DedicacionModel(codigo="TIEMPO COMPLETO", nombre="TIEMPO COMPLETO")
            cat_auxiliar = CategoriaModel(codigo="AUXILIAR", nombre="AUXILIAR")
            cat_tecnico = CategoriaModel(codigo="TECNICO DOCENTE", nombre="TÉCNICO DOCENTE")
            sesion.add_all(
                [
                    pao,
                    fac_a,
                    fac_b,
                    carrera_a,
                    carrera_b,
                    docente,
                    titular,
                    tc,
                    cat_auxiliar,
                    cat_tecnico,
                ]
            )
            await sesion.flush()

            # Fila principal: FCII, 30h, categoria auxiliar.
            sesion.add(
                FilaDistributivoModel(
                    docente_id=docente.id,
                    pao_id=pao.id,
                    facultad_id=fac_a.id,
                    carrera_id=carrera_a.id,
                    titularidad_id=titular.id,
                    dedicacion_id=tc.id,
                    categoria_id=cat_auxiliar.id,
                    horas_docencia={"Da": 10.0},
                    total_docencia=20.0,
                    total_investigacion=5.0,
                    total_horas=30.0,
                )
            )
            # Segunda fila, con menos horas y una categoria de tecnico
            # docente: no debe ganar la representacion, pero si debe marcar
            # `es_tecnico_docente` en True para el docente entero.
            sesion.add(
                FilaDistributivoModel(
                    docente_id=docente.id,
                    pao_id=pao.id,
                    facultad_id=fac_b.id,
                    carrera_id=carrera_b.id,
                    titularidad_id=titular.id,
                    dedicacion_id=tc.id,
                    categoria_id=cat_tecnico.id,
                    horas_docencia={"Da": 2.0},
                    total_docencia=5.0,
                    total_horas=5.0,
                    estado_validacion="OK",
                )
            )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            resumen = await repo.docentes_resumen([pao.id])

            assert len(resumen) == 1
            d = resumen[0]
            assert d.facultad_codigo == "FCII"
            assert d.categoria == "AUXILIAR"
            assert d.da == 12.0
            assert d.d == 25.0
            assert d.i == 5.0
            assert d.tot == 35.0
            assert d.es_tecnico_docente is True
            assert set(d.carreras.split(", ")) == {"SISTEMAS", "ARQUITECTURA"}
    finally:
        await motor.dispose()


async def test_docentes_resumen_marca_es_directivo_cuando_tiene_cargo(
    esquema: None,
) -> None:  # type: ignore[no-untyped-def]
    """Una fila con `cargo_directivo_id` basta para marcar `es_directivo` en
    todo el docente, igual que `es_tecnico_docente` con la categoria."""
    from app.core.config import get_settings
    from app.infrastructure.db.analitica_distributivo import RepositorioAnaliticaDistributivoSQL
    from app.infrastructure.db.modelos_distributivo import (
        CargoDirectivoModel,
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
            carrera = CarreraModel(codigo="SISTEMAS", nombre="SISTEMAS")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            decano = CargoDirectivoModel(codigo="DECANO", nombre="DECANO")
            sesion.add_all([pao, facultad, carrera, docente, decano])
            await sesion.flush()

            sesion.add(
                FilaDistributivoModel(
                    docente_id=docente.id,
                    pao_id=pao.id,
                    facultad_id=facultad.id,
                    carrera_id=carrera.id,
                    cargo_directivo_id=decano.id,
                    horas_docencia={"Da": 4.0},
                    total_docencia=4.0,
                    total_horas=4.0,
                )
            )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            resumen = await repo.docentes_resumen([pao.id])

            assert len(resumen) == 1
            assert resumen[0].es_directivo is True
            assert resumen[0].cargo_directivo == "DECANO"
    finally:
        await motor.dispose()


async def test_docentes_resumen_no_duplica_una_carga_combinada(
    esquema: None,
) -> None:  # type: ignore[no-untyped-def]
    """Misma regla que `_suma_sin_duplicar`: una carga repartida en varias
    filas por `grupo_combinado_id` se suma una sola vez por docente."""
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
            resumen = await repo.docentes_resumen([pao.id])

            assert len(resumen) == 1
            assert resumen[0].tot == 8.0
            assert resumen[0].da == 8.0

            # El desglose por carrera, en cambio, no dedup lica: cada fila ya
            # es su propia carrera.
            split = await repo.split_por_carrera([pao.id])
            assert {s.carrera for s in split} == {"UIO:A - GRADO", "UIO:B - GRADO"}
            assert all(s.tot == 8.0 for s in split)
    finally:
        await motor.dispose()


async def test_split_por_carrera_trae_una_fila_por_carrera(esquema: None) -> None:  # type: ignore[no-untyped-def]
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
            carrera = CarreraModel(codigo="SISTEMAS", nombre="SISTEMAS")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            sesion.add_all([pao, facultad, carrera, docente])
            await sesion.flush()

            sesion.add(
                FilaDistributivoModel(
                    docente_id=docente.id,
                    pao_id=pao.id,
                    facultad_id=facultad.id,
                    carrera_id=carrera.id,
                    horas_docencia={"Da": 12.0},
                    total_docencia=24.0,
                    total_horas=40.0,
                )
            )
            await sesion.commit()

            repo = RepositorioAnaliticaDistributivoSQL(sesion)
            split = await repo.split_por_carrera([pao.id])

            assert len(split) == 1
            assert split[0].carrera == "SISTEMAS"
            assert split[0].carrera_id == carrera.id
            assert split[0].facultad_codigo == "FCII"
            assert split[0].da == 12.0
            assert split[0].tot == 40.0
            assert split[0].es_tecnico_docente is False
    finally:
        await motor.dispose()
