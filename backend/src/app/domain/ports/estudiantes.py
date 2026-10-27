"""Puertos de la matricula estudiantil."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities.estudiantes import Estudiante, MatriculaEstudiante


@dataclass(frozen=True, slots=True)
class ConteoPorCarrera:
    """Estudiantes matriculados en una carrera, para un periodo dado.

    La usa el futuro Tablero Docente para calcular la relacion
    estudiantes/docente por carrera. Solo cuenta matriculas con `matriculado
    = "MATRICULADO"` y `carrera_id` resuelto: las de estado `REGISTRADO (OP)`
    aun no son una matricula efectiva, y las que no encontraron coincidencia
    en `cat_carreras` no pueden agruparse por el.
    """

    carrera_id: UUID
    total_estudiantes: int


class RepositorioEstudiantes(Protocol):
    """Estudiantes y sus matriculas, con upsert por lote para la importacion."""

    async def obtener_por_cedula(self, cedula: str) -> Estudiante | None:
        """El primer estudiante con esa cedula, si existe.

        La cedula no es unica -ver `Estudiante`-, asi que esto es una
        resolucion de identidad best-effort y no una busqueda por clave:
        sirve para no crear un estudiante nuevo en cada recarga del padron.
        """
        ...

    async def importar_lote(
        self,
        estudiantes: Sequence[Estudiante],
        matriculas: Sequence[MatriculaEstudiante],
    ) -> tuple[int, int]:
        """Hace upsert de los estudiantes y de sus matriculas.

        Los estudiantes se insertan o actualizan por `id` -ya resuelto por el
        caso de uso contra `obtener_por_cedula`-. Las matriculas, por su clave
        natural `(estudiante_id, periodo, carrera, sede)`; sus becas, anidadas
        en cada `MatriculaEstudiante.becas`, se reemplazan enteras -se borran
        las que tuviera la matricula y se insertan las del archivo-.

        Devuelve `(matriculas_creadas, matriculas_actualizadas)`.
        """
        ...

    async def conteo_por_carrera(
        self, periodo: str, carreras_ids: Sequence[UUID] = ()
    ) -> list[ConteoPorCarrera]:
        """Estudiantes matriculados por carrera, para ese periodo.

        `carreras_ids` vacio no filtra: trae todas las carreras con
        matriculas en ese periodo.
        """
        ...

    async def conteo_por_carrera_en_semestres(
        self, prefijos_periodo: Sequence[str], carreras_ids: Sequence[UUID] = ()
    ) -> list[ConteoPorCarrera]:
        """Estudiantes matriculados por carrera, en todo un semestre.

        El periodo de Banner no calza con el codigo de `cat_paos` en el
        digito de nivel (ver el docstring de la migracion de
        `matriculas_estudiante`), pero los dos primeros bloques -anio y
        periodo del anio- ocupan la misma posicion en ambos esquemas:
        `261651` y `261751` son los dos `2026-1`. Por eso aqui no se compara
        el periodo completo, sino su prefijo de tres caracteres, para poder
        sumar los estudiantes de un semestre sin adivinar a que nivel de
        Banner corresponde cada periodo del distributivo.

        `prefijos_periodo` vacio no trae nada -a diferencia de
        `carreras_ids`, un prefijo vacio no significa «todos»-.
        """
        ...
