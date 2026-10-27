"""Esquemas de salida del Tablero Docente.

Aparte de `distributivo.py` —que ya pasa de 850 lineas— porque esta pantalla
tiene su propio payload, sin relacion con los esquemas de filas o catalogos
que viven alli.
"""

from __future__ import annotations

from uuid import UUID

from app.api.esquemas.comunes import EsquemaBase
from app.api.esquemas.distributivo import PeriodoDisponibleSalida
from app.domain.ports.analitica import (
    DocenteResumen,
    EstudiantesPorCarrera,
    FilaSplitCarrera,
    TableroDocente,
)


class DocenteResumenSalida(EsquemaBase):
    """Un docente, con sus horas sumadas entre todas sus filas del grupo.

    Las formulas del tablero —topes, alertas, ETC— se calculan en el cliente
    a partir de estos campos; aqui solo se describen los datos crudos.
    """

    docente_id: UUID
    identificacion: str
    nombre_completo: str
    facultad_codigo: str
    facultad_nombre: str
    carreras: str
    sedes: str
    niveles: list[str]
    titularidad: str
    categoria: str
    dedicacion: str
    relacion_laboral: str
    cargo_directivo: str
    da: float
    d: float
    i: float
    v: float
    g: float
    tot: float
    es_tecnico_docente: bool
    es_directivo: bool
    es_valido: bool
    estado_validacion: str | None

    @classmethod
    def desde(cls, d: DocenteResumen) -> DocenteResumenSalida:
        return cls(
            docente_id=d.docente_id,
            identificacion=d.identificacion,
            nombre_completo=d.nombre_completo,
            facultad_codigo=d.facultad_codigo,
            facultad_nombre=d.facultad_nombre,
            carreras=d.carreras,
            sedes=d.sedes,
            niveles=list(d.niveles),
            titularidad=d.titularidad,
            categoria=d.categoria,
            dedicacion=d.dedicacion,
            relacion_laboral=d.relacion_laboral,
            cargo_directivo=d.cargo_directivo,
            da=d.da,
            d=d.d,
            i=d.i,
            v=d.v,
            g=d.g,
            tot=d.tot,
            es_tecnico_docente=d.es_tecnico_docente,
            es_directivo=d.es_directivo,
            es_valido=d.es_valido,
            estado_validacion=d.estado_validacion,
        )


class FilaSplitCarreraSalida(EsquemaBase):
    """Una fila docente x carrera x nivel x dedicacion, ya repartida."""

    docente_id: UUID
    facultad_codigo: str
    facultad_nombre: str
    carrera: str
    carrera_id: UUID
    sede: str
    nivel: str
    dedicacion: str
    titularidad: str
    categoria: str
    da: float
    d: float
    i: float
    v: float
    g: float
    tot: float
    es_tecnico_docente: bool

    @classmethod
    def desde(cls, f: FilaSplitCarrera) -> FilaSplitCarreraSalida:
        return cls(
            docente_id=f.docente_id,
            facultad_codigo=f.facultad_codigo,
            facultad_nombre=f.facultad_nombre,
            carrera=f.carrera,
            carrera_id=f.carrera_id,
            sede=f.sede,
            nivel=f.nivel,
            dedicacion=f.dedicacion,
            titularidad=f.titularidad,
            categoria=f.categoria,
            da=f.da,
            d=f.d,
            i=f.i,
            v=f.v,
            g=f.g,
            tot=f.tot,
            es_tecnico_docente=f.es_tecnico_docente,
        )


class EstudiantesPorCarreraSalida(EsquemaBase):
    """Estudiantes matriculados en una carrera, en el semestre que se examina."""

    carrera_id: UUID
    total_estudiantes: int

    @classmethod
    def desde(cls, e: EstudiantesPorCarrera) -> EstudiantesPorCarreraSalida:
        return cls(carrera_id=e.carrera_id, total_estudiantes=e.total_estudiantes)


class TableroDocenteSalida(EsquemaBase):
    """Todo lo que pinta el Tablero Docente, en una sola respuesta.

    `docentes` es el grupo que se examina y `docentes_anterior` el de
    comparacion; `split` solo trae el grupo que se examina —las pestanas que
    lo usan no comparan periodos—.
    """

    periodos: list[PeriodoDisponibleSalida]
    docentes: list[DocenteResumenSalida]
    docentes_anterior: list[DocenteResumenSalida]
    split: list[FilaSplitCarreraSalida]
    estudiantes_por_carrera: list[EstudiantesPorCarreraSalida]
    codigos_actual: list[str]
    codigos_anterior: list[str]
    generado_en: str

    @classmethod
    def desde(cls, t: TableroDocente) -> TableroDocenteSalida:
        return cls(
            periodos=[
                PeriodoDisponibleSalida(
                    id=p.id, codigo=p.codigo, nombre=p.nombre, semestre=p.semestre, filas=p.filas
                )
                for p in t.periodos
            ],
            docentes=[DocenteResumenSalida.desde(d) for d in t.docentes],
            docentes_anterior=[DocenteResumenSalida.desde(d) for d in t.docentes_anterior],
            split=[FilaSplitCarreraSalida.desde(f) for f in t.split],
            estudiantes_por_carrera=[
                EstudiantesPorCarreraSalida.desde(e) for e in t.estudiantes_por_carrera
            ],
            codigos_actual=list(t.codigos_actual),
            codigos_anterior=list(t.codigos_anterior),
            generado_en=t.generado_en,
        )
