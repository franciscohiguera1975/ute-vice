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

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.casos_uso.analitica import (
    EntradaResumenComparativo,
    EntradaTableroDistributivo,
    ObtenerResumenComparativo,
    ObtenerTableroDistributivo,
)
from app.domain.enums import FormatoReporte, Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.analitica import (
    RepositorioAnaliticaDistributivo,
    ResumenComparativo,
    TableroDistributivo,
    ValidacionDeGrupo,
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
#: Las dos tablas del tablero, para que tambien se puedan bajar.
RESUMEN_APROBACION = "aprobacion"
RESUMEN_COMPARATIVO = "comparativo"


@dataclass(frozen=True, slots=True)
class EntradaExportarResumen:
    grupo_a: tuple[UUID, ...] = ()
    grupo_b: tuple[UUID, ...] = ()
    dedicacion_ids: tuple[UUID, ...] = ()
    """Solo se aplica a los resumenes (`avance`, `estados`); el tablero no la usa."""
    resumen: str = RESUMEN_AVANCE
    grupo: str = "b"
    """Para el resumen de estados: cual de los dos grupos se desglosa."""

    etiqueta_a: str = ""
    etiqueta_b: str = ""
    """Como titular cada grupo en las columnas. Vacio usa el semestre.

    Lo elige quien exporta porque la pantalla lo deja editar: un grupo puede
    reunir periodos de varios semestres, y entonces ningun rotulo automatico
    dice lo que el usuario tenia en la cabeza al armarlo.
    """

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
        # Cada tabla sale del **mismo caso de uso que alimenta su pantalla**:
        # las dos del tablero, del tablero; las dos de resumenes, de resumenes.
        # El archivo no puede decir otra cosa que lo que se esta viendo, y dos
        # caminos distintos al mismo numero acaban divergiendo.
        constructor_tablero = _DEL_TABLERO.get(entrada.resumen)
        if constructor_tablero is not None:
            tablero = await ObtenerTableroDistributivo(self._analitica, self._reloj)(
                EntradaTableroDistributivo(grupo_a=entrada.grupo_a, grupo_b=entrada.grupo_b),
                contexto,
            )
            tabla = constructor_tablero(tablero, entrada, contexto)
            if not tabla.filas:
                raise ErrorValidacion(
                    "No hay datos para exportar con los periodos elegidos", campo="grupos"
                )
            tabla.generado_en = self._reloj.ahora()
            return self._exportadores.obtener(entrada.formato).exportar(tabla)

        datos = await ObtenerResumenComparativo(self._analitica, self._reloj)(
            EntradaResumenComparativo(
                grupo_a=entrada.grupo_a,
                grupo_b=entrada.grupo_b,
                dedicacion_ids=entrada.dedicacion_ids,
            ),
            contexto,
        )
        constructor = _DE_RESUMENES.get(entrada.resumen, _tabla_de_avance)

        tabla = constructor(datos, entrada, contexto)

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


def _semestres(codigos: Sequence[str]) -> str:
    """Los semestres que reune un grupo: `262651` y `262151` son `2026-2`.

    Es el rotulo por defecto de las columnas. Seis codigos no caben en una
    cabecera; el semestre si, y es como se nombra el periodo al hablarlo.
    """
    vistos: list[str] = []
    for codigo in codigos:
        if len(codigo) < 3:
            continue
        semestre = f"20{codigo[:2]}-{codigo[2]}"
        if semestre not in vistos:
            vistos.append(semestre)
    return " · ".join(vistos)


def _rotulo(entrada: EntradaExportarResumen, grupo: str, codigos: Sequence[str]) -> str:
    """Como se titula un grupo: lo que pidio quien exporta, o el semestre."""
    elegido = (entrada.etiqueta_a if grupo == "a" else entrada.etiqueta_b).strip()
    return elegido or _semestres(codigos) or f"grupo {1 if grupo == 'a' else 2}"


def _tabla_de_avance(
    datos: ResumenComparativo, entrada: EntradaExportarResumen, contexto: ContextoEjecucion
) -> TablaReporte:
    uno, dos = _codigos(datos, "a"), _codigos(datos, "b")
    # Los titulos llevan el semestre y no los codigos: un grupo son hasta seis,
    # y la cabecera acabaria ocupando mas que los datos. Los codigos viajan en
    # el subtitulo y en la constancia de filtros, que es donde se buscan.
    rotulo_a = _rotulo(entrada, "a", datos.grupo_a.codigos if datos.grupo_a else ())
    rotulo_b = _rotulo(entrada, "b", datos.grupo_b.codigos if datos.grupo_b else ())

    columnas = [
        ColumnaReporte("facultad", "Facultad", 12, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("nombre", "Nombre de la facultad", 46, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("docentes_a", f"Docentes {rotulo_a}", 18, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte(
            "docentes_b", f"Docentes {rotulo_b}", 18, "numero", "derecha", _PASTEL_VERDE
        ),
        ColumnaReporte(
            "aprobadas_b", f"Aprobadas {rotulo_b}", 19, "numero", "derecha", _PASTEL_VERDE_CLARO
        ),
        ColumnaReporte("aprobado", "% Aprobado", 12, "porcentaje", "derecha", _PASTEL_AMBAR),
    ]

    filas: list[dict[str, Any]] = [
        {
            "facultad": a.codigo,
            "nombre": a.nombre,
            "docentes_a": a.docentes_a,
            "docentes_b": a.docentes_b,
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
    aprobadas = sum(a.filas_aprobadas_b for a in datos.avance)
    evaluadas = sum(a.filas_evaluadas_b for a in datos.avance)
    totales = {
        f"Suma de la columna, {rotulo_a}": sum(a.docentes_a for a in datos.avance),
        f"Suma de la columna, {rotulo_b}": sum(a.docentes_b for a in datos.avance),
        f"Docentes distintos, {rotulo_a}": distintos_a,
        f"Docentes distintos, {rotulo_b}": distintos_b,
        f"Aprobadas {rotulo_b}": aprobadas,
        "% Aprobado": round(aprobadas / evaluadas * 100, 1) if evaluadas else 0.0,
    }

    return TablaReporte(
        titulo="Avance del distributivo por facultad",
        subtitulo=f"{rotulo_a}: {uno}   ·   {rotulo_b}: {dos}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados={rotulo_a: uno, rotulo_b: dos},
        generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
        totales=totales,
        color_banda=_BANDA,
    )


def _tabla_de_estados(
    datos: ResumenComparativo, entrada: EntradaExportarResumen, contexto: ContextoEjecucion
) -> TablaReporte:
    grupo = entrada.grupo
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


def _codigos_del_tablero(tablero: TableroDistributivo, grupo: str) -> str:
    validacion = tablero.anterior if grupo == "a" else tablero.actual
    return " · ".join(validacion.codigos) if validacion else "sin periodos"


def _tabla_de_aprobacion(
    tablero: TableroDistributivo,
    entrada: EntradaExportarResumen,
    contexto: ContextoEjecucion,
) -> TablaReporte:
    """La comparativa por facultad del tablero: filas, aprobadas y variacion."""
    uno, dos = _codigos_del_tablero(tablero, "a"), _codigos_del_tablero(tablero, "b")
    rotulo_a = _rotulo(entrada, "a", tablero.anterior.codigos if tablero.anterior else ())
    rotulo_b = _rotulo(entrada, "b", tablero.actual.codigos if tablero.actual else ())

    columnas = [
        ColumnaReporte("facultad", "Facultad", 46, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("filas_b", f"Filas {rotulo_b}", 16, "numero", "derecha", _PASTEL_VERDE),
        ColumnaReporte(
            "aprobado_b", f"% Aprobado {rotulo_b}", 20, "porcentaje", "derecha", _PASTEL_VERDE_CLARO
        ),
        ColumnaReporte("filas_a", f"Filas {rotulo_a}", 16, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte(
            "aprobado_a", f"% Aprobado {rotulo_a}", 20, "porcentaje", "derecha", _PASTEL_AZUL
        ),
        ColumnaReporte(
            "variacion", "Variacion (puntos)", 18, "porcentaje", "derecha", _PASTEL_AMBAR
        ),
    ]

    # `actual` es el grupo 2 y `anterior` el grupo 1. El archivo se queda con
    # la nomenclatura del selector, que es la que el usuario acaba de usar.
    filas: list[dict[str, Any]] = [
        {
            "facultad": f.etiqueta,
            "filas_b": f.total_actual,
            "aprobado_b": f.porcentaje_actual if f.evaluadas_actual else None,
            "filas_a": f.total_anterior,
            "aprobado_a": f.porcentaje_anterior if f.evaluadas_anterior else None,
            "variacion": f.variacion if f.evaluadas_actual and f.evaluadas_anterior else None,
        }
        for f in tablero.por_facultad
    ]

    actual, anterior = tablero.actual, tablero.anterior
    totales = {
        f"Filas {rotulo_b}": actual.total if actual else 0,
        f"Filas {rotulo_a}": anterior.total if anterior else 0,
        f"Docentes distintos, {rotulo_b}": actual.docentes if actual else 0,
        f"Docentes distintos, {rotulo_a}": anterior.docentes if anterior else 0,
        f"% Aprobado {rotulo_b}": (
            actual.porcentaje_aprobado if actual and actual.evaluadas else 0.0
        ),
    }

    return TablaReporte(
        titulo="Aprobacion del distributivo por facultad",
        subtitulo=f"{rotulo_a}: {uno}   ·   {rotulo_b}: {dos}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados={rotulo_a: uno, rotulo_b: dos},
        generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
        totales=totales,
        color_banda=_BANDA,
    )


#: Etiqueta legible de cada estado, en el orden en que se leen.
_ORDEN_ESTADOS: tuple[tuple[str, str], ...] = (
    ("OK", "Validado"),
    ("OK_EXCEPCION", "Validado con excepcion"),
    ("PENDIENTE", "Validacion pendiente"),
    ("ERROR", "Con error"),
    ("SIN_ESTADO", "Sin estado registrado"),
)


def _tabla_comparativa_de_estados(
    tablero: TableroDistributivo,
    entrada: EntradaExportarResumen,
    contexto: ContextoEjecucion,
) -> TablaReporte:
    """El desglose por estado del tablero: un estado por fila, dos grupos.

    Es la otra orientacion de `_tabla_de_estados`, que reparte por facultad.
    Las dos hacen falta: una responde «que facultad va atrasada» y la otra
    «en que estado esta el periodo».
    """
    uno, dos = _codigos_del_tablero(tablero, "a"), _codigos_del_tablero(tablero, "b")
    rotulo_a = _rotulo(entrada, "a", tablero.anterior.codigos if tablero.anterior else ())
    rotulo_b = _rotulo(entrada, "b", tablero.actual.codigos if tablero.actual else ())

    columnas = [
        ColumnaReporte("estado", "Estado", 26, "texto", "izquierda", _AZUL_OSCURO),
        ColumnaReporte("filas_b", f"Filas {rotulo_b}", 16, "numero", "derecha", _PASTEL_VERDE),
        ColumnaReporte("pct_b", f"% {rotulo_b}", 14, "porcentaje", "derecha", _PASTEL_VERDE_CLARO),
        ColumnaReporte("filas_a", f"Filas {rotulo_a}", 16, "numero", "derecha", _PASTEL_AZUL),
        ColumnaReporte("pct_a", f"% {rotulo_a}", 14, "porcentaje", "derecha", _PASTEL_AZUL),
    ]

    def contar(validacion: ValidacionDeGrupo | None) -> tuple[dict[str, int], int]:
        if validacion is None:
            return {}, 0
        return {c.etiqueta: c.valor for c in validacion.por_estado}, validacion.total

    conteo_b, total_b = contar(tablero.actual)
    conteo_a, total_a = contar(tablero.anterior)

    filas: list[dict[str, Any]] = [
        {
            "estado": etiqueta,
            "filas_b": conteo_b.get(codigo, 0),
            "pct_b": round(conteo_b.get(codigo, 0) / total_b * 100, 1) if total_b else None,
            "filas_a": conteo_a.get(codigo, 0),
            "pct_a": round(conteo_a.get(codigo, 0) / total_a * 100, 1) if total_a else None,
        }
        for codigo, etiqueta in _ORDEN_ESTADOS
    ]

    return TablaReporte(
        titulo="Estados del distributivo",
        subtitulo=f"{rotulo_a}: {uno}   ·   {rotulo_b}: {dos}",
        columnas=columnas,
        filas=filas,
        filtros_aplicados={rotulo_a: uno, rotulo_b: dos},
        generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
        totales={f"Total {rotulo_b}": total_b, f"Total {rotulo_a}": total_a},
        color_banda=_BANDA,
    )


#: Cada resumen con la tabla que lo construye, agrupados por la pantalla de la
#: que salen. Agregar uno es una linea en el diccionario que corresponda.
_DE_RESUMENES: dict[
    str, Callable[[ResumenComparativo, EntradaExportarResumen, ContextoEjecucion], TablaReporte]
] = {
    RESUMEN_AVANCE: _tabla_de_avance,
    RESUMEN_ESTADOS: _tabla_de_estados,
}

_DEL_TABLERO: dict[
    str, Callable[[TableroDistributivo, EntradaExportarResumen, ContextoEjecucion], TablaReporte]
] = {
    RESUMEN_APROBACION: _tabla_de_aprobacion,
    RESUMEN_COMPARATIVO: _tabla_comparativa_de_estados,
}
