"""`conteo_por_carrera_en_semestres`, la consulta que conecta la matricula
estudiantil con el Tablero Docente.

Necesita PostgreSQL real porque ejercita `LEFT(periodo, 3)`, una funcion de
texto que los dobles en memoria no reproducen igual.
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


async def test_agrupa_por_prefijo_de_semestre_y_excluye_lo_que_no_cuenta(
    esquema: None,
) -> None:  # type: ignore[no-untyped-def]
    """Dos periodos de Banner del mismo semestre -`262651` grado, `262751`
    posgrado- se suman juntos con un solo prefijo `"262"`, aunque sus
    digitos de nivel no calcen con los de `cat_paos`. Una matricula de otro
    semestre, una sin `carrera_id` resuelto y una `REGISTRADO (OP)` no
    cuentan.
    """
    from app.core.config import get_settings
    from app.infrastructure.db.modelos_distributivo import CarreraModel
    from app.infrastructure.db.modelos_estudiantes import EstudianteModel, MatriculaEstudianteModel
    from app.infrastructure.db.repositorios.estudiantes import RepositorioEstudiantesSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        async with fabrica() as sesion:
            sistemas = CarreraModel(codigo="SISTEMAS", nombre="SISTEMAS")
            derecho = CarreraModel(codigo="DERECHO", nombre="DERECHO")
            sesion.add_all([sistemas, derecho])
            await sesion.flush()

            def estudiante(cedula: str) -> EstudianteModel:
                return EstudianteModel(cedula=cedula, nombre=cedula)

            e1, e2, e3, e4, e5 = (estudiante(f"170000000{i}") for i in range(5))
            sesion.add_all([e1, e2, e3, e4, e5])
            await sesion.flush()

            sesion.add_all(
                [
                    # Dos matriculas de SISTEMAS en el mismo semestre 2026-2,
                    # una en grado («262651») y otra en posgrado («262751»):
                    # deben sumarse con el prefijo «262».
                    MatriculaEstudianteModel(
                        estudiante_id=e1.id,
                        periodo="262651",
                        carrera="SISTEMAS",
                        carrera_id=sistemas.id,
                        matriculado="MATRICULADO",
                    ),
                    MatriculaEstudianteModel(
                        estudiante_id=e2.id,
                        periodo="262751",
                        carrera="SISTEMAS",
                        carrera_id=sistemas.id,
                        matriculado="MATRICULADO",
                    ),
                    # Otro semestre: no debe contar en el prefijo «262».
                    MatriculaEstudianteModel(
                        estudiante_id=e3.id,
                        periodo="261651",
                        carrera="SISTEMAS",
                        carrera_id=sistemas.id,
                        matriculado="MATRICULADO",
                    ),
                    # Sin carrera reconocida: no se puede agrupar.
                    MatriculaEstudianteModel(
                        estudiante_id=e4.id,
                        periodo="262651",
                        carrera="UNA CARRERA QUE NO EXISTE",
                        carrera_id=None,
                        matriculado="MATRICULADO",
                    ),
                    # Registrada pero no matriculada: aun no es efectiva.
                    MatriculaEstudianteModel(
                        estudiante_id=e5.id,
                        periodo="262651",
                        carrera="SISTEMAS",
                        carrera_id=sistemas.id,
                        matriculado="REGISTRADO (OP)",
                    ),
                ]
            )
            await sesion.commit()

            repo = RepositorioEstudiantesSQL(sesion)
            conteos = await repo.conteo_por_carrera_en_semestres(("262",))

            assert len(conteos) == 1
            assert conteos[0].carrera_id == sistemas.id
            assert conteos[0].total_estudiantes == 2

            # Filtrado por carreras_ids: una carrera sin matriculas en el
            # prefijo no aparece, en vez de salir con cero.
            vacio = await repo.conteo_por_carrera_en_semestres(("262",), (derecho.id,))
            assert vacio == []

            # Sin prefijos, no trae nada -a diferencia de `carreras_ids`
            # vacio, que no filtra-.
            assert await repo.conteo_por_carrera_en_semestres(()) == []
    finally:
        await motor.dispose()


async def test_importar_no_revienta_con_filas_que_repiten_la_matricula(
    esquema: None,
) -> None:  # type: ignore[no-untyped-def]
    """Reproduce el `CardinalityViolationError` de produccion: dos filas del
    archivo con la misma clave natural -estudiante, periodo, carrera, sede-,
    cada una con una beca distinta en vez de concatenadas en la misma celda.

    `ON CONFLICT DO UPDATE` de Postgres rechaza una sentencia que le pide
    actualizar la misma fila dos veces; `ImportarEstudiantes` tiene que
    fusionarlas antes de llegar al upsert, no dejar que el repositorio se
    entere de dos matriculas con la misma clave.
    """
    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.importar_estudiantes import (
        EntradaImportacionEstudiantes,
        ImportarEstudiantes,
    )
    from app.core.config import get_settings
    from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
    from app.domain.ports.importacion_estudiantes import BecaCruda, FilaCrudaEstudiante
    from app.infrastructure.db.uow import UnidadDeTrabajoSQL

    motor, fabrica = await _sesion(get_settings())
    try:
        uow = UnidadDeTrabajoSQL(fabrica)
        async with uow:
            await uow.catalogos.agregar(
                ElementoCatalogo(tipo=TipoCatalogo.CARRERA, codigo="MEDICINA", nombre="MEDICINA")
            )
            await uow.commit()

        def fila(numero: int, beca: BecaCruda) -> FilaCrudaEstudiante:
            return FilaCrudaEstudiante(
                numero_fila=numero,
                periodo="262651",
                cedula="1710034065",
                sede="SEDE QUITO",
                carrera="MEDICINA",
                nombre="PEREZ LUIS",
                matriculado="MATRICULADO",
                becas=(beca,),
            )

        caso = ImportarEstudiantes(uow)
        resultado = await caso(
            EntradaImportacionEstudiantes(
                filas=(
                    fila(2, BecaCruda(codigo_beca="B1", tipo_beca="DEPORTIVA", porcentaje="50")),
                    fila(3, BecaCruda(codigo_beca="B2", tipo_beca="HERMANO", porcentaje="10")),
                )
            ),
            ContextoEjecucion.sistema(),
        )

        assert resultado.matriculas_creadas == 1
        assert resultado.filas_combinadas_por_duplicado == 1
        assert resultado.becas_creadas == 2
    finally:
        await motor.dispose()
