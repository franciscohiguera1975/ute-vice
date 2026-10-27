"""`RepositorioDistributivoSQL.filas_resueltas`, con el catalogo de cargos
directivos.

Esta consulta resuelve todos los catalogos de una fila con columnas por
posicion (`_consulta_resuelta`/`_a_resuelta`): agregar un catalogo nuevo
corre el riesgo de desplazar los indices de los que ya estaban. Se prueba
contra PostgreSQL real y no en memoria porque lo que importa aqui es el SQL
que arma la consulta, no la logica de Python alrededor.
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


async def test_filas_resueltas_resuelve_el_cargo_directivo(esquema: None) -> None:  # type: ignore[no-untyped-def]
    """Una fila con `cargo_directivo_id` sale de `filas_resueltas` con el
    nombre del cargo ya resuelto a texto, y el resto de catalogos —que ya
    estaban antes de este campo— siguen resolviendose en su columna correcta.
    """
    from app.core.config import get_settings
    from app.domain.ports.distributivo import FiltroDistributivo
    from app.infrastructure.db.modelos_distributivo import (
        CargoDirectivoModel,
        CarreraModel,
        CategoriaModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        GeneroModel,
        PaoModel,
        TitularidadModel,
    )
    from app.infrastructure.db.repositorios.distributivo import RepositorioDistributivoSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            pao = PaoModel(codigo="262651", nombre="2026-2 GRADO")
            facultad = FacultadModel(codigo="FCII", nombre="FCII")
            carrera = CarreraModel(codigo="SISTEMAS", nombre="SISTEMAS")
            docente = DocenteModel(identificacion="1710034065", nombre_completo="PEREZ LUIS")
            titular = TitularidadModel(codigo="TITULAR", nombre="TITULAR")
            categoria = CategoriaModel(codigo="AUXILIAR", nombre="AUXILIAR")
            genero = GeneroModel(codigo="MASCULINO", nombre="MASCULINO")
            decano = CargoDirectivoModel(codigo="DECANO", nombre="DECANO")
            sesion.add_all([pao, facultad, carrera, docente, titular, categoria, genero, decano])
            await sesion.flush()
            docente.genero_id = genero.id

            fila = FilaDistributivoModel(
                docente_id=docente.id,
                pao_id=pao.id,
                facultad_id=facultad.id,
                carrera_id=carrera.id,
                titularidad_id=titular.id,
                categoria_id=categoria.id,
                cargo_directivo_id=decano.id,
                total_horas=10.0,
            )
            sesion.add(fila)
            await sesion.commit()

            repo = RepositorioDistributivoSQL(sesion)
            resueltas = await repo.filas_resueltas(FiltroDistributivo(pao_id=pao.id))

            assert len(resueltas) == 1
            r = resueltas[0]
            # El catalogo nuevo, resuelto a texto.
            assert r.cargo_directivo == "DECANO"
            assert r.fila.cargo_directivo_id == decano.id
            # Los catalogos que ya estaban antes no se corrieron de indice.
            assert r.titularidad == "TITULAR"
            assert r.categoria == "AUXILIAR"
            assert r.genero == "MASCULINO"
            assert r.docente_identificacion == "1710034065"
    finally:
        await motor.dispose()


async def test_filas_resueltas_sin_cargo_directivo_sale_en_none(esquema: None) -> None:  # type: ignore[no-untyped-def]
    """Una fila sin cargo directivo no rompe la resolucion: el campo sale en
    `None`, igual que cualquier otro catalogo opcional sin informar."""
    from app.core.config import get_settings
    from app.domain.ports.distributivo import FiltroDistributivo
    from app.infrastructure.db.modelos_distributivo import (
        CarreraModel,
        DocenteModel,
        FacultadModel,
        FilaDistributivoModel,
        PaoModel,
    )
    from app.infrastructure.db.repositorios.distributivo import RepositorioDistributivoSQL

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
                    total_horas=10.0,
                )
            )
            await sesion.commit()

            repo = RepositorioDistributivoSQL(sesion)
            resueltas = await repo.filas_resueltas(FiltroDistributivo(pao_id=pao.id))

            assert len(resueltas) == 1
            assert resueltas[0].cargo_directivo is None
            assert resueltas[0].fila.cargo_directivo_id is None
    finally:
        await motor.dispose()
