"""Exportacion del distributivo a archivo.

El caso de uso no sabe que columnas salen: resuelve los filtros, le pide el
contenido a la plantilla elegida y se lo entrega al exportador del formato. Las
plantillas viven en `app.application.plantillas` y se registran alli.

Asi, sumar un formato nuevo —y van a hacer falta mas— no toca este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.plantillas import (
    REGISTRO_PLANTILLAS,
    ContenidoPlantilla,
    PlantillaDistributivo,
    RegistroPlantillas,
)
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.enums import FormatoReporte, Permiso
from app.domain.errors import ErrorValidacion, NoEncontrado, ReporteDemasiadoGrande
from app.domain.ports.distributivo import FiltroDistributivo
from app.domain.ports.reloj import Reloj
from app.domain.ports.reportes import (
    ArchivoReporte,
    ColumnaReporte,
    RegistroExportadores,
    TablaReporte,
)
from app.domain.ports.uow import UnidadDeTrabajo

#: Cuantas filas pinta la vista previa.
_FILAS_VISTA_PREVIA = 50


@dataclass(frozen=True, slots=True)
class EntradaReporteDistributivo:
    """Filtros del reporte.

    `carrera_ids` admite varias carreras: es como se emite el reporte, una
    facultad con el conjunto de sus programas.
    """

    pao_id: UUID
    facultad_id: UUID | None = None
    carrera_ids: tuple[UUID, ...] = ()
    plantilla: str | None = None
    """Codigo de la plantilla. Vacio usa la institucional."""

    formato: FormatoReporte = FormatoReporte.XLSX
    incluir_columnas_auditoria: bool = False
    """Agrega identificacion, carrera y total de horas al final del archivo."""


@dataclass(frozen=True, slots=True)
class PlantillaDisponible:
    """Una plantilla, como la ve quien va a elegirla."""

    codigo: str
    nombre: str
    descripcion: str
    admite_auditoria: bool


@dataclass(frozen=True, slots=True)
class VistaPreviaReporte:
    """Lo que saldria en el reporte, para revisarlo antes de descargarlo."""

    plantilla: str = ""
    nombre_plantilla: str = ""
    columnas: list[ColumnaReporte] = field(default_factory=list)
    filas: list[dict[str, object]] = field(default_factory=list)
    total_filas: int = 0
    total_docentes: int = 0
    sin_asignatura: int = 0
    sin_anio_inicio: int = 0
    periodo: str = ""
    facultad: str | None = None
    carreras: list[str] = field(default_factory=list)

    @property
    def esta_completo(self) -> bool:
        return self.sin_asignatura == 0


class ListarPlantillasReporte(CasoDeUso[None, list[PlantillaDisponible]]):
    """Que formatos de exportacion hay."""

    nombre = "reportes.distributivo_plantillas"
    descripcion = "Lista las plantillas de exportacion del distributivo"
    permiso_requerido = Permiso.REPORTES_GENERAR

    def __init__(self, registro: RegistroPlantillas = REGISTRO_PLANTILLAS) -> None:
        self._registro = registro

    async def _ejecutar(
        self, entrada: None, contexto: ContextoEjecucion
    ) -> list[PlantillaDisponible]:
        return [
            PlantillaDisponible(
                codigo=p.codigo,
                nombre=p.nombre,
                descripcion=p.descripcion,
                admite_auditoria=p.admite_auditoria,
            )
            for p in self._registro.disponibles()
        ]


class _BaseReporteDistributivo:
    """Resuelve filtros y delega el contenido en la plantilla."""

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        reloj: Reloj,
        plantillas: RegistroPlantillas = REGISTRO_PLANTILLAS,
    ) -> None:
        self._uow = uow
        self._reloj = reloj
        self._plantillas = plantillas

    async def _resolver(
        self, entrada: EntradaReporteDistributivo, *, limite: int | None
    ) -> tuple[PlantillaDistributivo, ContenidoPlantilla, str, str | None, list[str]]:
        plantilla = self._plantillas.obtener(entrada.plantilla)

        async with self._uow:
            pao = await self._uow.catalogos.obtener(TipoCatalogo.PAO, entrada.pao_id)
            if pao is None:
                raise NoEncontrado("periodo academico", entrada.pao_id)

            facultad = None
            if entrada.facultad_id:
                elemento = await self._uow.catalogos.obtener(
                    TipoCatalogo.FACULTAD, entrada.facultad_id
                )
                if elemento is None:
                    raise NoEncontrado("facultad", entrada.facultad_id)
                facultad = elemento.nombre

            carreras: list[str] = []
            for carrera_id in entrada.carrera_ids:
                elemento = await self._uow.catalogos.obtener(TipoCatalogo.CARRERA, carrera_id)
                if elemento is None:
                    raise NoEncontrado("carrera", carrera_id)
                carreras.append(elemento.nombre)

            contenido = await plantilla.construir(
                self._uow,
                FiltroDistributivo(
                    pao_id=entrada.pao_id,
                    facultad_id=entrada.facultad_id,
                    carrera_ids=entrada.carrera_ids,
                ),
                incluir_auditoria=entrada.incluir_columnas_auditoria,
                limite=limite,
            )

        return plantilla, contenido, pao.codigo, facultad, carreras


class VistaPreviaReporteDistributivo(
    _BaseReporteDistributivo, CasoDeUso[EntradaReporteDistributivo, VistaPreviaReporte]
):
    """Muestra el reporte antes de generarlo.

    Sirve para ver cuantas filas saldrian sin asignatura, que es el dato que
    obliga a completar informacion antes de enviar el archivo.
    """

    nombre = "reportes.distributivo_vista_previa"
    descripcion = "Previsualiza una exportacion del distributivo"
    permiso_requerido = Permiso.REPORTES_GENERAR

    async def _ejecutar(
        self, entrada: EntradaReporteDistributivo, contexto: ContextoEjecucion
    ) -> VistaPreviaReporte:
        plantilla, contenido, periodo, facultad, carreras = await self._resolver(
            entrada, limite=_FILAS_VISTA_PREVIA
        )
        return VistaPreviaReporte(
            plantilla=plantilla.codigo,
            nombre_plantilla=plantilla.nombre,
            columnas=contenido.columnas,
            filas=contenido.filas,
            total_filas=contenido.total_filas,
            total_docentes=contenido.total_docentes,
            sin_asignatura=contenido.sin_asignatura,
            sin_anio_inicio=contenido.sin_anio_inicio,
            periodo=periodo,
            facultad=facultad,
            carreras=carreras,
        )


class GenerarReporteDistributivo(
    _BaseReporteDistributivo, CasoDeUso[EntradaReporteDistributivo, ArchivoReporte]
):
    """Genera el archivo con la plantilla elegida."""

    nombre = "reportes.distributivo"
    descripcion = "Exporta el distributivo con una plantilla"
    permiso_requerido = Permiso.REPORTES_GENERAR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        exportadores: RegistroExportadores,
        reloj: Reloj,
        plantillas: RegistroPlantillas = REGISTRO_PLANTILLAS,
        max_filas: int = 100_000,
    ) -> None:
        super().__init__(uow, reloj, plantillas)
        self._exportadores = exportadores
        self._max_filas = max_filas

    async def _ejecutar(
        self, entrada: EntradaReporteDistributivo, contexto: ContextoEjecucion
    ) -> ArchivoReporte:
        plantilla, contenido, periodo, facultad, carreras = await self._resolver(
            entrada, limite=None
        )

        if not contenido.filas:
            raise ErrorValidacion(
                "No hay docentes que cumplan los filtros seleccionados. "
                "Revise el periodo, la facultad y las carreras.",
                campo="filtros",
            )
        if contenido.total_filas > self._max_filas:
            raise ReporteDemasiadoGrande(contenido.total_filas, self._max_filas)

        tabla = TablaReporte(
            titulo=plantilla.titulo,
            subtitulo=self._subtitulo(periodo, facultad, carreras),
            columnas=contenido.columnas,
            filas=contenido.filas,
            filtros_aplicados=self._filtros(plantilla, periodo, facultad, carreras),
            generado_en=self._reloj.ahora(),
            generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
            totales=contenido.totales,
            solo_datos=plantilla.solo_datos,
        )
        return self._exportadores.obtener(entrada.formato).exportar(tabla)

    # ------------------------------------------------------------ internos
    @staticmethod
    def _subtitulo(periodo: str, facultad: str | None, carreras: list[str]) -> str:
        partes = [f"Periodo {periodo}"]
        if facultad:
            partes.append(facultad)
        if carreras:
            partes.append(carreras[0] if len(carreras) == 1 else f"{len(carreras)} carreras")
        return " · ".join(partes)

    @staticmethod
    def _filtros(
        plantilla: PlantillaDistributivo,
        periodo: str,
        facultad: str | None,
        carreras: list[str],
    ) -> dict[str, object]:
        filtros: dict[str, object] = {"Plantilla": plantilla.nombre, "Periodo": periodo}
        if facultad:
            filtros["Facultad"] = facultad
        if carreras:
            # Se listan por nombre, no por cantidad: un reporte sin constancia de
            # que carreras incluye no se puede contrastar con otro.
            filtros["Carreras"] = "; ".join(carreras)
        return filtros
