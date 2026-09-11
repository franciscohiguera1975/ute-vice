"""Casos de uso de generacion de reportes.

Un caso de uso por tipo de reporte, todos con la misma estructura: consultar,
armar una `TablaReporte` y delegar el formato al exportador. El formato de
salida es un parametro, no una rama del codigo — asi agregar PDF, ODS o lo que
venga no obliga a tocar estos casos de uso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.titulo import Titulo
from app.domain.enums import EstadoTitulo, FormatoReporte, Permiso
from app.domain.errors import ReporteDemasiadoGrande
from app.domain.ports.reloj import Reloj
from app.domain.ports.reportes import (
    ArchivoReporte,
    ColumnaReporte,
    RegistroExportadores,
    TablaReporte,
)
from app.domain.ports.repositorios import (
    FiltroLogs,
    FiltroPersonas,
    FiltroTitulos,
    Paginacion,
)
from app.domain.ports.uow import UnidadDeTrabajo

#: Tamano de lote al paginar sobre el repositorio para armar un reporte grande.
_LOTE = 200


@dataclass(frozen=True, slots=True)
class EntradaReportePersonas:
    formato: FormatoReporte = FormatoReporte.XLSX
    filtro: FiltroPersonas = field(default_factory=FiltroPersonas)
    incluir_titulos: bool = False
    """Genera una fila por titulo en lugar de una por persona."""


@dataclass(frozen=True, slots=True)
class EntradaReporteTitulos:
    formato: FormatoReporte = FormatoReporte.XLSX
    filtro: FiltroTitulos = field(default_factory=FiltroTitulos)


@dataclass(frozen=True, slots=True)
class EntradaReporteConsultas:
    formato: FormatoReporte = FormatoReporte.XLSX
    filtro: FiltroLogs = field(default_factory=FiltroLogs)


# ---------------------------------------------------------------------------


class _BaseReporte:
    """Comportamiento comun: limite de filas y volcado paginado."""

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        exportadores: RegistroExportadores,
        reloj: Reloj,
        max_filas: int = 100_000,
    ) -> None:
        self._uow = uow
        self._exportadores = exportadores
        self._reloj = reloj
        self._max_filas = max_filas

    def _verificar_tamano(self, total: int) -> None:
        if total > self._max_filas:
            raise ReporteDemasiadoGrande(total, self._max_filas)

    def _exportar(self, tabla: TablaReporte, formato: FormatoReporte) -> ArchivoReporte:
        return self._exportadores.obtener(formato).exportar(tabla)

    @staticmethod
    def _autor(contexto: ContextoEjecucion) -> str:
        return contexto.actor.nombre_completo if contexto.actor else "Sistema"


class GenerarReportePersonas(_BaseReporte, CasoDeUso[EntradaReportePersonas, ArchivoReporte]):
    """Padron de personas, opcionalmente desglosado por titulo."""

    nombre = "reportes.personas"
    descripcion = "Genera el reporte del padron de personas"
    permiso_requerido = Permiso.REPORTES_GENERAR

    _COLUMNAS: ClassVar[list[ColumnaReporte]] = [
        ColumnaReporte("cedula", "Cedula", 14),
        ColumnaReporte("apellidos", "Apellidos", 26),
        ColumnaReporte("nombres", "Nombres", 26),
        ColumnaReporte("vinculacion", "Vinculacion", 18),
        ColumnaReporte("unidad", "Unidad", 30),
        ColumnaReporte("cargo", "Cargo", 26),
        ColumnaReporte("email", "Correo institucional", 32),
        ColumnaReporte("titulos", "Titulos", 10, tipo="numero", alineacion="centro"),
        ColumnaReporte("ultima_consulta", "Ultima consulta", 18, tipo="fecha_hora"),
        ColumnaReporte("estado_consulta", "Estado", 18),
        ColumnaReporte("activo", "Activo", 10, tipo="booleano", alineacion="centro"),
    ]

    _COLUMNAS_CON_TITULOS: ClassVar[list[ColumnaReporte]] = [
        *_COLUMNAS[:7],
        ColumnaReporte("titulo", "Titulo", 42),
        ColumnaReporte("institucion", "Institucion", 34),
        ColumnaReporte("nivel", "Nivel", 18),
        ColumnaReporte("registro", "N. registro", 18),
        ColumnaReporte("fecha_registro", "Fecha registro", 16, tipo="fecha"),
        ColumnaReporte("estado_titulo", "Estado titulo", 16),
    ]

    async def _ejecutar(
        self, entrada: EntradaReportePersonas, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        async with self._uow:
            primera = await self._uow.personas.listar(
                entrada.filtro, Paginacion(pagina=1, tamano=1)
            )
            self._verificar_tamano(primera.total)

            filas: list[dict[str, Any]] = []
            pagina = 1
            while True:
                lote = await self._uow.personas.listar(
                    entrada.filtro, Paginacion(pagina=pagina, tamano=_LOTE)
                )
                for persona in lote.items:
                    base = {
                        "cedula": persona.cedula.valor,
                        "apellidos": persona.nombre.apellidos,
                        "nombres": persona.nombre.nombres,
                        "vinculacion": persona.tipo_vinculacion.value,
                        "unidad": persona.unidad or "",
                        "cargo": persona.cargo or "",
                        "email": str(persona.email_institucional or ""),
                    }
                    if not entrada.incluir_titulos:
                        filas.append(
                            {
                                **base,
                                "titulos": persona.titulos_registrados,
                                "ultima_consulta": persona.ultima_consulta_en,
                                "estado_consulta": (
                                    persona.ultima_consulta_estado.value
                                    if persona.ultima_consulta_estado
                                    else "SIN CONSULTAR"
                                ),
                                "activo": persona.activo,
                            }
                        )
                        continue

                    titulos = await self._uow.titulos.listar_por_persona(persona.id)
                    if not titulos:
                        # Una persona sin titulos igual aparece: su ausencia es
                        # justamente el dato que el reporte debe evidenciar.
                        filas.append({**base, "titulo": "(sin titulos registrados)"})
                        continue
                    filas.extend(
                        {
                            **base,
                            "titulo": t.denominacion,
                            "institucion": t.institucion,
                            "nivel": t.nivel.value,
                            "registro": t.numero_registro or "",
                            "fecha_registro": t.fecha_registro,
                            "estado_titulo": t.estado.value,
                        }
                        for t in titulos
                    )

                if not lote.tiene_siguiente:
                    break
                pagina += 1

        tabla = TablaReporte(
            titulo="Padron de personal",
            subtitulo=(
                "Detalle por titulo academico" if entrada.incluir_titulos else "Resumen por persona"
            ),
            columnas=(self._COLUMNAS_CON_TITULOS if entrada.incluir_titulos else self._COLUMNAS),
            filas=filas,
            filtros_aplicados=_describir_filtro(entrada.filtro),
            generado_en=self._reloj.ahora(),
            generado_por=self._autor(contexto),
            totales={"Registros": len(filas)},
        )
        return self._exportar(tabla, entrada.formato)


class GenerarReporteTitulos(_BaseReporte, CasoDeUso[EntradaReporteTitulos, ArchivoReporte]):
    """Inventario de titulos con los datos de su titular."""

    nombre = "reportes.titulos"
    descripcion = "Genera el reporte de titulos academicos"
    permiso_requerido = Permiso.REPORTES_GENERAR

    _COLUMNAS: ClassVar[list[ColumnaReporte]] = [
        ColumnaReporte("cedula", "Cedula", 14),
        ColumnaReporte("persona", "Titular", 34),
        ColumnaReporte("denominacion", "Titulo", 44),
        ColumnaReporte("institucion", "Institucion", 34),
        ColumnaReporte("nivel", "Nivel", 18),
        ColumnaReporte("area", "Area", 26),
        ColumnaReporte("registro", "N. registro", 18),
        ColumnaReporte("fecha_registro", "Fecha registro", 16, tipo="fecha"),
        ColumnaReporte("origen", "Origen", 14),
        ColumnaReporte("estado", "Estado", 16),
        ColumnaReporte("verificado", "Verificado", 12, tipo="booleano", alineacion="centro"),
    ]

    async def _ejecutar(
        self, entrada: EntradaReporteTitulos, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        async with self._uow:
            primera = await self._uow.titulos.listar(entrada.filtro, Paginacion(pagina=1, tamano=1))
            self._verificar_tamano(primera.total)

            filas: list[dict[str, Any]] = []
            cache_personas: dict[Any, tuple[str, str]] = {}
            pagina = 1
            while True:
                lote = await self._uow.titulos.listar(
                    entrada.filtro, Paginacion(pagina=pagina, tamano=_LOTE)
                )
                for titulo in lote.items:
                    if titulo.persona_id not in cache_personas:
                        persona = await self._uow.personas.obtener(titulo.persona_id)
                        cache_personas[titulo.persona_id] = (
                            (persona.cedula.valor, persona.nombre.formal)
                            if persona
                            else ("", "(persona no encontrada)")
                        )
                    cedula, nombre = cache_personas[titulo.persona_id]
                    filas.append(_fila_titulo(titulo, cedula, nombre))

                if not lote.tiene_siguiente:
                    break
                pagina += 1

        tabla = TablaReporte(
            titulo="Inventario de titulos academicos",
            columnas=self._COLUMNAS,
            filas=filas,
            filtros_aplicados=_describir_filtro(entrada.filtro),
            generado_en=self._reloj.ahora(),
            generado_por=self._autor(contexto),
            totales={
                "Titulos": len(filas),
                "Vigentes": sum(1 for f in filas if f["estado"] == EstadoTitulo.VIGENTE.value),
                "Retirados": sum(1 for f in filas if f["estado"] == EstadoTitulo.RETIRADO.value),
            },
        )
        return self._exportar(tabla, entrada.formato)


class GenerarReporteConsultas(_BaseReporte, CasoDeUso[EntradaReporteConsultas, ArchivoReporte]):
    """Bitacora de consultas: el reporte de auditoria del proceso."""

    nombre = "reportes.consultas"
    descripcion = "Genera el reporte del historico de consultas"
    permiso_requerido = Permiso.REPORTES_GENERAR

    _COLUMNAS: ClassVar[list[ColumnaReporte]] = [
        ColumnaReporte("fecha", "Fecha", 20, tipo="fecha_hora"),
        ColumnaReporte("cedula", "Cedula", 14),
        ColumnaReporte("estado", "Estado", 20),
        ColumnaReporte("proveedor", "Proveedor", 16),
        ColumnaReporte("encontrados", "Encontrados", 12, tipo="numero", alineacion="centro"),
        ColumnaReporte("nuevos", "Nuevos", 10, tipo="numero", alineacion="centro"),
        ColumnaReporte("modificados", "Modificados", 12, tipo="numero", alineacion="centro"),
        ColumnaReporte("retirados", "Retirados", 11, tipo="numero", alineacion="centro"),
        ColumnaReporte("duracion", "Duracion (ms)", 14, tipo="numero", alineacion="derecha"),
        ColumnaReporte("intento", "Intento", 9, tipo="numero", alineacion="centro"),
        ColumnaReporte("mensaje", "Detalle", 50),
    ]

    async def _ejecutar(
        self, entrada: EntradaReporteConsultas, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        async with self._uow:
            primera = await self._uow.logs.listar(entrada.filtro, Paginacion(pagina=1, tamano=1))
            self._verificar_tamano(primera.total)

            filas: list[dict[str, Any]] = []
            pagina = 1
            while True:
                lote = await self._uow.logs.listar(
                    entrada.filtro, Paginacion(pagina=pagina, tamano=_LOTE)
                )
                filas.extend(
                    {
                        "fecha": registro.iniciado_en,
                        "cedula": registro.cedula.valor,
                        "estado": registro.estado.value,
                        "proveedor": registro.proveedor,
                        "encontrados": registro.titulos_encontrados,
                        "nuevos": registro.titulos_nuevos,
                        "modificados": registro.titulos_actualizados,
                        "retirados": registro.titulos_retirados,
                        "duracion": registro.duracion_ms or 0,
                        "intento": registro.intento,
                        "mensaje": registro.resumen,
                    }
                    for registro in lote.items
                )
                if not lote.tiene_siguiente:
                    break
                pagina += 1

        tabla = TablaReporte(
            titulo="Historico de consultas al registro nacional",
            columnas=self._COLUMNAS,
            filas=filas,
            filtros_aplicados=_describir_filtro(entrada.filtro),
            generado_en=self._reloj.ahora(),
            generado_por=self._autor(contexto),
            totales={
                "Consultas": len(filas),
                "Con error": sum(1 for f in filas if "ERROR" in f["estado"]),
            },
        )
        return self._exportar(tabla, entrada.formato)


class ListarFormatosDisponibles(CasoDeUso[None, list[str]]):
    """Formatos de exportacion habilitados en esta instalacion."""

    nombre = "reportes.formatos"
    descripcion = "Lista los formatos de exportacion disponibles"
    permiso_requerido = Permiso.REPORTES_GENERAR

    def __init__(self, exportadores: RegistroExportadores) -> None:
        self._exportadores = exportadores

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[str]:
        return [f.value for f in self._exportadores.formatos_disponibles()]


# ---------------------------------------------------------------------------


def _fila_titulo(titulo: Titulo, cedula: str, nombre: str) -> dict[str, Any]:
    return {
        "cedula": cedula,
        "persona": nombre,
        "denominacion": titulo.denominacion,
        "institucion": titulo.institucion,
        "nivel": titulo.nivel.value,
        "area": titulo.area_conocimiento or "",
        "registro": titulo.numero_registro or "",
        "fecha_registro": titulo.fecha_registro,
        "origen": titulo.origen.value,
        "estado": titulo.estado.value,
        "verificado": titulo.verificado,
    }


def _describir_filtro(filtro: object) -> dict[str, Any]:
    """Serializa los filtros aplicados para imprimirlos en la cabecera.

    Un reporte sin constancia de sus filtros no es auditable: quien lo reciba no
    puede saber si "45 personas sin titulo" son todas o solo las de una unidad.
    """
    from dataclasses import asdict, is_dataclass

    if not is_dataclass(filtro) or isinstance(filtro, type):
        return {}
    return {
        clave: (valor.value if hasattr(valor, "value") else valor)
        for clave, valor in asdict(filtro).items()
        if valor is not None and valor is not False
    }
