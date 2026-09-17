"""Exportacion de los resumenes del distributivo.

Los resumenes son agregados —una fila por facultad—, no filas del distributivo,
asi que no pasan por las plantillas de `reporte_distributivo`. Lo que si
comparten es el puerto de exportacion: se arma una `TablaReporte` y el formato
lo decide el exportador, con lo que xlsx, csv y pdf salen de un solo camino.

## La paleta

Las columnas se agrupan por bloques de color porque la tabla mezcla tres cosas
distintas: lo que tenia el primer grupo, lo que tiene el segundo y que parte de
eso esta aprobada. Sin el color hay que leer la cabecera entera para saber a
que grupo pertenece cada cifra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.casos_uso.analitica import (
    EntradaResumenComparativo,
    ObtenerResumenComparativo,
)
from app.domain.enums import FormatoReporte, Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.analitica import (
    RepositorioAnaliticaDistributivo,
    ResumenComparativo,
)
from app.domain.ports.reloj import Reloj
from app.domain.ports.reportes import (
    ArchivoReporte,
    ColumnaReporte,
    RegistroExportadores,
    TablaReporte,
)

# Tonos pastel: la cabecera distingue bloques y la banda acompana sin competir
# con el texto. El exportador elige letra blanca o negra segun la luminancia.
_AZUL_OSCURO = "1F3864"
_PASTEL_AZUL = "BDD7EE"
_PASTEL_VERDE = "C6E0B4"
_PASTEL_VERDE_CLARO = "E2EFDA"
_PASTEL_AMBAR = "FFE699"
_PASTEL_SALMON = "F8CBAD"
_PASTEL_GRIS = "E7E6E6"
_BANDA = "EAF3FA"

#: Los resumenes que se pueden exportar. Mismos codigos que usa la pantalla.
RESUMEN_AVANCE = "avance"
RESUMEN_ESTADOS = "estados"


@dataclass(frozen=True, slots=True)
class EntradaExportarResumen:
    grupo_a: tuple[UUID, ...] = ()
    grupo_b: tuple[UUID, ...] = ()
    resumen: str = RESUMEN_AVANCE
    grupo: str = "b"
    """Para el resumen de estados: cual de los dos grupos se desglosa."""
    formato: FormatoReporte = FormatoReporte.XLSX


class ExportarResumenDistributivo(CasoDeUso[EntradaExportarResumen, ArchivoReporte]):
    """Genera el archivo del resumen que se este viendo."""

    nombre = "analitica.exportar_resumen"
    descripcion = "Exporta un resumen comparativo del distributivo"
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
        self, entrada: EntradaExportarResumen, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        # Se reutiliza el caso de uso de lectura en lugar de repetir su
        # consulta: el archivo tiene que decir exactamente lo mismo que la
        # pantalla, y dos caminos distintos acabarian divergiendo.
        datos = await ObtenerResumenComparativo(self._analitica, self._reloj)(
            EntradaResumenComparativo(grupo_a=entrada.grupo_a, grupo_b=entrada.grupo_b),
            contexto,
        )

        if entrada.resumen == RESUMEN_ESTADOS:
            tabla = _tabla_de_estados(datos, entrada.grupo, contexto)
        else:
            tabla = _tabla_de_avance(datos, contexto)

        if not tabla.filas:
            raise ErrorValidacion(
                "No hay datos para exportar con los periodos elegidos", campo="grupos"
            )

        tabla.generado_en = self._reloj.ahora()
        return self._exportadores.obtener(entrada.formato).exportar(tabla)


# ---------------------------------------------------------------------------
# Construccion de las tablas
# ---------------------------------------------------------------------------


def _codigos(datos: ResumenComparativo, grupo: str) -> str:
    elegido = datos.grupo_a if grupo == "a" else datos.grupo_b
    return " · ".join(elegido.codigos) if elegido and elegido.codigos else "sin periodos"


def _tabla_de_avance(datos: ResumenComparativo, contexto: ContextoEjecucion) -> TablaReporte:
    uno, dos = _codigos(datos, "a"), _codigos(datos, "b")

    columnas = [
        ColumnaReporte("facultad", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("nombre", "Nombre de la facultad", 46, "texto", "izquierda", _AZUL_OSCURO),
        # Los titulos no llevan los codigos: un grupo son hasta seis, y la
        # cabecera acabaria ocupando mas que los datos. Los codigos viajan en
        # el subtitulo y en la constancia de filtros, que es donde se buscan.
        ColumnaReporte("docentes_a", "Docentes grupo 1", 17, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte("docentes_b", "Docentes grupo 2", 17, "numero", "derecha", _PASTEL_VERDE),
        ColumnaReporte("avance", "% Avance", 11, "porcentaje", "derecha", _PASTEL_AMBAR),
        ColumnaReporte("filas_b", "Filas grupo 2", 14, "numero", "derecha", _PASTEL_VERDE_CLARO),
        ColumnaReporte(
            "aprobadas_b", "Aprobadas grupo 2", 18, "numero", "derecha", _PASTEL_VERDE_CLARO
        ),
        ColumnaReporte("aprobado", "% Aprobado", 12, "porcentaje", "derecha", _PASTEL_AMBAR),
    ]

    filas: list[dict[str, Any]] = [
        {
            "facultad": a.codigo,
            "nombre": a.nombre,
            "docentes_a": a.docentes_a,
            "docentes_b": a.docentes_b,
            "avance": a.porcentaje_avance if a.docentes_a else None,
            "filas_b": a.filas_b,
            "aprobadas_b": a.filas_aprobadas_b,
            "aprobado": a.porcentaje_aprobado_b if a.filas_evaluadas_b else None,
        }
        for a in datos.avance
    ]

    # Los dos totales van como pie y no como una fila mas: sumar la columna de
    # docentes no da los docentes distintos —quien dicta en dos facultades
    # cuenta dos veces— y mezclarlos en la tabla invita a leer mal el archivo.
    distintos_a = datos.grupo_a.docentes if datos.grupo_a else 0
    distintos_b = datos.grupo_b.docentes if datos.grupo_b else 0
    totales = {
        "Suma de la columna, grupo 1": sum(a.docentes_a for a in datos.avance),
        "Suma de la columna, grupo 2": sum(a.docentes_b for a in datos.avance),
        "Docentes distintos, grupo 1": distintos_a,
        "Docentes distintos, grupo 2": distintos_b,
        "% Avance sobre docentes distintos": (
            round(distintos_b / distintos_a * 100, 1) if distintos_a else 0.0
        ),
    }

    return TablaReporte(
        titulo="Avance del distributivo por facultad",
        subtitulo=f"Grupo 1: {uno}   ·   Grupo 2: {dos}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados={"Grupo 1": uno, "Grupo 2": dos},
        generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
        totales=totales,
        color_banda=_BANDA,
    )


def _tabla_de_estados(
    datos: ResumenComparativo, grupo: str, contexto: ContextoEjecucion
) -> TablaReporte:
    filas_origen = datos.estados_a if grupo == "a" else datos.estados_b
    periodos = _codigos(datos, grupo)

    columnas = [
        ColumnaReporte("facultad", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("nombre", "Nombre de la facultad", 46, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("ok", "Validado", 11, "numero", "derecha", _PASTEL_VERDE),
        ColumnaReporte("excepcion", "Con excepcion", 14, "numero", "derecha", _PASTEL_VERDE_CLARO),
        ColumnaReporte("pendiente", "Pendiente", 12, "numero", "derecha", _PASTEL_AMBAR),
        ColumnaReporte("error", "Con error", 11, "numero", "derecha", _PASTEL_SALMON),
        ColumnaReporte("sin_estado", "Sin estado", 12, "numero", "derecha", _PASTEL_GRIS),
        ColumnaReporte("total", "Total", 10, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte("aprobado", "% Aprobado", 12, "porcentaje", "derecha", _PASTEL_AZUL),
    ]

    filas: list[dict[str, Any]] = [
        {
            "facultad": e.codigo,
            "nombre": e.nombre,
            "ok": e.ok,
            "excepcion": e.ok_excepcion,
            "pendiente": e.pendiente,
            "error": e.con_error,
            "sin_estado": e.sin_estado,
            "total": e.total,
            "aprobado": e.porcentaje_aprobado if e.evaluadas else None,
        }
        for e in filas_origen
    ]

    evaluadas = sum(e.evaluadas for e in filas_origen)
    aprobadas = sum(e.ok + e.ok_excepcion for e in filas_origen)
    totales = {
        "Validadas": sum(e.ok for e in filas_origen),
        "Con excepcion": sum(e.ok_excepcion for e in filas_origen),
        "Pendientes": sum(e.pendiente for e in filas_origen),
        "Con error": sum(e.con_error for e in filas_origen),
        "Sin estado registrado": sum(e.sin_estado for e in filas_origen),
        "Total de filas": sum(e.total for e in filas_origen),
        "% Aprobado sobre las evaluadas": (
            round(aprobadas / evaluadas * 100, 1) if evaluadas else 0.0
        ),
    }

    return TablaReporte(
        titulo="Estados del distributivo por facultad",
        subtitulo=f"Periodos: {periodos}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados={"Periodos": periodos},
        generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
        totales=totales,
        color_banda=_BANDA,
    )
