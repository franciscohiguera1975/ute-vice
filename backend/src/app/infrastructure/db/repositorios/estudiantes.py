"""Repositorio de la matricula estudiantil sobre PostgreSQL."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.estudiantes import Estudiante, MatriculaEstudiante
from app.domain.ports.estudiantes import ConteoPorCarrera
from app.infrastructure.db import mapeadores_estudiantes as m
from app.infrastructure.db.modelos_estudiantes import (
    BecaEstudianteModel,
    EstudianteModel,
    MatriculaEstudianteModel,
)

#: Columnas que se escriben en el upsert de `estudiantes`. La `id` no esta
#: aqui: es el criterio del conflicto, no un valor que cambie.
_COLUMNAS_ESTUDIANTE = (
    "cedula",
    "id_banner",
    "nombre",
    "genero_id",
    "mail_personal",
    "mail_ute",
    "telefono_celular",
    "telefono_fijo",
    "fecha_nacimiento",
)

#: Columnas que se escriben en el upsert de `matriculas_estudiante`. La clave
#: natural -estudiante, periodo, carrera, sede- no esta aqui: es lo que
#: identifica la fila, no lo que cambia.
_COLUMNAS_MATRICULA = (
    "facultad",
    "carrera_id",
    "tipo_carrera",
    "modalidad",
    "nivel_formacion_1",
    "nivel_formacion_2",
    "tipo_estudiante",
    "sistema",
    "matriculado",
    "solicitud_retiro",
    "bloqueo_plataforma",
    "estado",
)


class RepositorioEstudiantesSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener_por_cedula(self, cedula: str) -> Estudiante | None:
        # La primera fila creada: no hay unicidad que garantice una sola, asi
        # que se elige de forma deterministica para no crear un estudiante
        # nuevo en cada recarga del padron.
        fila = await self._s.scalar(
            select(EstudianteModel)
            .where(EstudianteModel.cedula == cedula)
            .order_by(EstudianteModel.creado_en)
            .limit(1)
        )
        return m.estudiante_a_dominio(fila) if fila else None

    # ------------------------------------------------------------ escritura
    async def importar_lote(
        self,
        estudiantes: Sequence[Estudiante],
        matriculas: Sequence[MatriculaEstudiante],
    ) -> tuple[int, int]:
        await self._upsert_estudiantes(estudiantes)
        if not matriculas:
            return (0, 0)

        altas, cambios, ids_reales = await self._upsert_matriculas(matriculas)
        await self._guardar_becas(matriculas, ids_reales)
        return (altas, cambios)

    async def _upsert_estudiantes(self, estudiantes: Sequence[Estudiante]) -> None:
        if not estudiantes:
            return

        for inicio in range(0, len(estudiantes), 500):
            lote = estudiantes[inicio : inicio + 500]
            registros = [
                {c: getattr(m.estudiante_a_modelo(e), c) for c in ("id", *_COLUMNAS_ESTUDIANTE)}
                for e in lote
            ]
            insercion = pg_insert(EstudianteModel).values(registros)
            sentencia = insercion.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    **{c: getattr(insercion.excluded, c) for c in _COLUMNAS_ESTUDIANTE},
                    "actualizado_en": func.now(),
                },
            )
            await self._s.execute(sentencia)

    async def _upsert_matriculas(
        self, matriculas: Sequence[MatriculaEstudiante]
    ) -> tuple[int, int, dict[UUID, UUID]]:
        """Upsert por la clave natural `(estudiante, periodo, carrera, sede)`.

        Devuelve ademas `ids_reales`: el `id` que de verdad quedo persistido
        para cada matricula -el propuesto por el caso de uso en un alta, o el
        que ya tenia la fila en un cambio-. Hace falta porque las becas de la
        misma importacion se enlazan por ese id real, no por el propuesto: en
        PostgreSQL, `ON CONFLICT DO UPDATE` conserva el id de la fila
        existente, no el del `VALUES` que la choco.
        """
        altas = cambios = 0
        ids_reales: dict[UUID, UUID] = {}
        claves = ("id", "estudiante_id", "periodo", "sede", "carrera")

        for inicio in range(0, len(matriculas), 500):
            lote = matriculas[inicio : inicio + 500]
            registros = [
                {
                    c: getattr(m.matricula_a_modelo(matricula), c)
                    for c in (*claves, *_COLUMNAS_MATRICULA)
                }
                for matricula in lote
            ]

            insercion = pg_insert(MatriculaEstudianteModel).values(registros)
            sentencia: Any = insercion.on_conflict_do_update(
                constraint="uq_matriculas_estudiante_natural",
                set_={
                    **{c: getattr(insercion.excluded, c) for c in _COLUMNAS_MATRICULA},
                    "actualizado_en": func.now(),
                },
            ).returning(MatriculaEstudianteModel.id, literal_column("(xmax = 0)").label("es_alta"))

            # El orden de retorno de un `INSERT ... VALUES (...), (...)` sigue
            # el orden de los valores: es lo que permite emparejar cada fila
            # del lote con el id que de verdad quedo persistido.
            resultado = (await self._s.execute(sentencia)).all()
            for matricula, (id_real, es_alta) in zip(lote, resultado, strict=True):
                ids_reales[matricula.id] = id_real
                if es_alta:
                    altas += 1
                else:
                    cambios += 1

        return (altas, cambios, ids_reales)

    async def _guardar_becas(
        self, matriculas: Sequence[MatriculaEstudiante], ids_reales: dict[UUID, UUID]
    ) -> None:
        """Reemplaza las becas de las matriculas tocadas por las del archivo.

        Se borra y se vuelve a insertar en lugar de comparar: la lista tiene
        pocos elementos, asi que reconstruirla sale mas simple que averiguar
        que cambio -mismo criterio que `_guardar_asignaturas` en el
        distributivo-.
        """
        ids_matriculas = list(ids_reales.values())
        if not ids_matriculas:
            return

        for inicio in range(0, len(ids_matriculas), 5_000):
            await self._s.execute(
                delete(BecaEstudianteModel).where(
                    BecaEstudianteModel.matricula_id.in_(ids_matriculas[inicio : inicio + 5_000])
                )
            )

        registros = [
            {
                "matricula_id": ids_reales[matricula.id],
                "codigo_beca": beca.codigo_beca,
                "financiamiento": beca.financiamiento,
                "tipo_beca": beca.tipo_beca,
                "porcentaje": beca.porcentaje,
            }
            for matricula in matriculas
            for beca in matricula.becas
        ]
        if not registros:
            return

        for inicio in range(0, len(registros), 5_000):
            await self._s.execute(insert(BecaEstudianteModel), registros[inicio : inicio + 5_000])

    # -------------------------------------------------------------- lectura
    async def conteo_por_carrera(
        self, periodo: str, carreras_ids: Sequence[UUID] = ()
    ) -> list[ConteoPorCarrera]:
        # Solo las matriculas efectivas -«MATRICULADO», no «REGISTRADO (OP)»-
        # y con carrera resuelta: las demas no pueden agruparse por catalogo.
        consulta = (
            select(MatriculaEstudianteModel.carrera_id, func.count())
            .where(
                MatriculaEstudianteModel.periodo == periodo,
                MatriculaEstudianteModel.carrera_id.isnot(None),
                MatriculaEstudianteModel.matriculado == "MATRICULADO",
            )
            .group_by(MatriculaEstudianteModel.carrera_id)
        )
        if carreras_ids:
            consulta = consulta.where(MatriculaEstudianteModel.carrera_id.in_(carreras_ids))

        filas = (await self._s.execute(consulta)).all()
        return [
            ConteoPorCarrera(carrera_id=carrera_id, total_estudiantes=int(total))
            for carrera_id, total in filas
        ]

    async def conteo_por_carrera_en_semestres(
        self, prefijos_periodo: Sequence[str], carreras_ids: Sequence[UUID] = ()
    ) -> list[ConteoPorCarrera]:
        if not prefijos_periodo:
            return []

        consulta = (
            select(MatriculaEstudianteModel.carrera_id, func.count())
            .where(
                func.left(MatriculaEstudianteModel.periodo, 3).in_(prefijos_periodo),
                MatriculaEstudianteModel.carrera_id.isnot(None),
                MatriculaEstudianteModel.matriculado == "MATRICULADO",
            )
            .group_by(MatriculaEstudianteModel.carrera_id)
        )
        if carreras_ids:
            consulta = consulta.where(MatriculaEstudianteModel.carrera_id.in_(carreras_ids))

        filas = (await self._s.execute(consulta)).all()
        return [
            ConteoPorCarrera(carrera_id=carrera_id, total_estudiantes=int(total))
            for carrera_id, total in filas
        ]
