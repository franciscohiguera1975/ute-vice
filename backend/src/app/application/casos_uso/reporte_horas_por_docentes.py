"""Exportacion de la pantalla de horas por docentes.

Las tres tablas de la pantalla —por facultad, por carrera y los docentes bajo
el umbral de horas— comparten el mismo caso de uso de lectura
(`ObtenerHorasPorDedicacion`): el archivo no puede decir otra cosa que lo que
se esta viendo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.casos_uso.analitica import (
    EntradaHorasPorDedicacion,
    ObtenerHorasPorDedicacion,
)
from app.domain.enums import FormatoReporte, Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.analitica import RepositorioAnaliticaDistributivo, ResumenDeHoras
from app.domain.ports.reloj import Reloj
from app.domain.ports.reportes import (
    ArchivoReporte,
    ColumnaReporte,
    RegistroExportadores,
    TablaReporte,
)

_AZUL_OSCURO = "1F3864"
_PASTEL_AZUL = "BDD7EE"
_PASTEL_VERDE = "C6E0B4"
_PASTEL_SALMON = "F8CBAD"
_BANDA = "EAF3FA"

#: Las tres tablas que se pueden exportar. Mismos codigos que usa la pantalla.
RESUMEN_FACULTAD = "facultad"
RESUMEN_CARRERA = "carrera"
RESUMEN_BAJO_HORAS = "bajo_horas"


@dataclass(frozen=True, slots=True)
class EntradaExportarHoras:
    grupo: tuple[UUID, ...] = ()
    dedicacion_id: UUID | None = None
    menos_de: float | None = None
    """Solo hace falta para `bajo_horas`; las otras dos tablas la ignoran."""
    excluir_sin_horas: bool = False
    """En `bajo_horas`, deja fuera a quien tiene 0 horas de Da."""
    resumen: str = RESUMEN_FACULTAD
    formato: FormatoReporte = FormatoReporte.XLSX


class ExportarHorasPorDocentes(CasoDeUso[EntradaExportarHoras, ArchivoReporte]):
    """Genera el archivo de la tabla de horas que se este viendo."""

    nombre = "analitica.exportar_horas_por_docentes"
    descripcion = "Exporta las horas por docentes del distributivo"
    permiso_requerido = Permiso.REPORTES_GENERAR

    def __init__(
        self,
        analitica: RepositorioAnaliticaDistributivo,
        exportadores: RegistroExportadores,
        reloj: Reloj,
    ) -> None:
        self._analitica = analitica
        self._exportadores = exportadores
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaExportarHoras, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        if entrada.resumen == RESUMEN_BAJO_HORAS and entrada.menos_de is None:
            raise ErrorValidacion(
                "Se necesita un umbral de horas para exportar este reporte", campo="menos_de"
            )

        datos = await ObtenerHorasPorDedicacion(self._analitica, self._reloj)(
            EntradaHorasPorDedicacion(
                grupo=entrada.grupo,
                dedicacion_id=entrada.dedicacion_id,
                menos_de=entrada.menos_de,
                excluir_sin_horas=entrada.excluir_sin_horas,
            ),
            contexto,
        )
        constructor = _CONSTRUCTORES.get(entrada.resumen, _tabla_por_facultad)
        tabla = constructor(datos, entrada, contexto)

        if not tabla.filas:
            raise ErrorValidacion(
                "No hay datos para exportar con los periodos y el filtro elegidos", campo="grupo"
            )

        tabla.generado_en = self._reloj.ahora()
        return self._exportadores.obtener(entrada.formato).exportar(tabla)


# ---------------------------------------------------------------------------
# Construccion de las tablas
# ---------------------------------------------------------------------------


def _codigos(datos: ResumenDeHoras) -> str:
    if not datos.grupo or not datos.grupo.codigos:
        return "sin periodos"
    return " · ".join(datos.grupo.codigos)


def _rotulo_dedicacion(entrada: EntradaExportarHoras) -> str:
    return "todas las dedicaciones" if entrada.dedicacion_id is None else "una dedicacion"


def _filtros(datos: ResumenDeHoras, entrada: EntradaExportarHoras) -> dict[str, Any]:
    return {"Periodos": _codigos(datos), "Dedicacion": _rotulo_dedicacion(entrada)}


def _generado_por(contexto: ContextoEjecucion) -> str:
    return contexto.actor.nombre_completo if contexto.actor else "Sistema"


def _tabla_por_facultad(
    datos: ResumenDeHoras, entrada: EntradaExportarHoras, contexto: ContextoEjecucion
) -> TablaReporte:
    columnas = [
        ColumnaReporte("codigo", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("nombre", "Nombre de la facultad", 46, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("docentes", "Docentes", 12, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte("horas_da", "Horas de Da", 14, "numero", "derecha", _PASTEL_VERDE),
    ]
    filas: list[dict[str, Any]] = [
        {"codigo": f.codigo, "nombre": f.nombre, "docentes": f.docentes, "horas_da": f.horas_da}
        for f in datos.por_facultad
    ]

    return TablaReporte(
        titulo="Horas por docentes, por facultad",
        subtitulo=f"Periodos: {_codigos(datos)}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados=_filtros(datos, entrada),
        generado_por=_generado_por(contexto),
        totales={"Docentes": datos.docentes, "Horas de Da": datos.horas_da},
        color_banda=_BANDA,
    )


def _tabla_por_carrera(
    datos: ResumenDeHoras, entrada: EntradaExportarHoras, contexto: ContextoEjecucion
) -> TablaReporte:
    columnas = [
        ColumnaReporte("facultad_codigo", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte(
            "facultad_nombre", "Nombre de la facultad", 40, "texto", "izquierda", _AZUL_OSCURO
        ),
        ColumnaReporte("carrera", "Carrera", 46, "texto", "izquierda", _PASTEL_AZUL),
        ColumnaReporte("docentes", "Docentes", 12, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte("horas_da", "Horas de Da", 14, "numero", "derecha", _PASTEL_VERDE),
    ]
    filas: list[dict[str, Any]] = [
        {
            "facultad_codigo": c.facultad_codigo,
            "facultad_nombre": c.facultad_nombre,
            "carrera": c.carrera,
            "docentes": c.docentes,
            "horas_da": c.horas_da,
        }
        for c in datos.por_carrera
    ]

    return TablaReporte(
        titulo="Horas por docentes, por carrera",
        subtitulo=f"Periodos: {_codigos(datos)}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados=_filtros(datos, entrada),
        generado_por=_generado_por(contexto),
        totales={"Docentes": datos.docentes, "Horas de Da": datos.horas_da},
        color_banda=_BANDA,
    )


def _tabla_bajo_horas(
    datos: ResumenDeHoras, entrada: EntradaExportarHoras, contexto: ContextoEjecucion
) -> TablaReporte:
    columnas = [
        ColumnaReporte("facultad_codigo", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte(
            "facultad_nombre", "Nombre de la facultad", 40, "texto", "izquierda", _AZUL_OSCURO
        ),
        ColumnaReporte("carrera", "Carrera", 46, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("identificacion", "Identificacion", 14, "texto", "izquierda", _PASTEL_AZUL),
        ColumnaReporte("docente", "Docente", 40, "texto", "izquierda", _PASTEL_AZUL),
        ColumnaReporte("horas_da", "Horas de Da", 14, "numero", "derecha", _PASTEL_SALMON),
    ]
    filas: list[dict[str, Any]] = [
        {
            "facultad_codigo": d.facultad_codigo,
            "facultad_nombre": d.facultad_nombre,
            "carrera": d.carrera,
            "identificacion": d.identificacion,
            "docente": d.docente,
            "horas_da": d.horas_da,
        }
        for d in datos.bajo_horas
    ]

    umbral = entrada.menos_de if entrada.menos_de is not None else 0.0
    filtros = _filtros(datos, entrada)
    filtros["Menos de"] = f"{umbral:g} horas de Da"
    filtros["Sin horas (0)"] = "Excluidos" if entrada.excluir_sin_horas else "Incluidos"

    return TablaReporte(
        titulo=f"Docentes con menos de {umbral:g} horas de Da",
        subtitulo=f"Periodos: {_codigos(datos)}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados=filtros,
        generado_por=_generado_por(contexto),
        totales={"Docentes": len(filas)},
        color_banda=_BANDA,
    )


_CONSTRUCTORES: dict[
    str, Callable[[ResumenDeHoras, EntradaExportarHoras, ContextoEjecucion], TablaReporte]
] = {
    RESUMEN_FACULTAD: _tabla_por_facultad,
    RESUMEN_CARRERA: _tabla_por_carrera,
    RESUMEN_BAJO_HORAS: _tabla_bajo_horas,
}
