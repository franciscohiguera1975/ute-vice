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
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
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

    Los tres admiten varios valores. Un reporte rara vez es de un periodo y una
    carrera: se emite una facultad con todos sus programas, o la evolucion de
    una carrera a lo largo de varios periodos. Obligar a generar un archivo por
    combinacion y pegarlos despues era el trabajo manual que esto evita.
    """

    pao_ids: tuple[UUID, ...] = ()
    facultad_ids: tuple[UUID, ...] = ()
    carrera_ids: tuple[UUID, ...] = ()
    plantilla: str | None = None
    """Codigo de la plantilla. Vacio usa la institucional."""

    formato: FormatoReporte = FormatoReporte.XLSX
    incluir_columnas_auditoria: bool = False
    """Agrega identificacion, carrera y total de horas al final del archivo."""


@dataclass(frozen=True, slots=True)
class _Seleccion:
    """Lo que se eligio, ya resuelto a texto.

    Viaja junto porque los tres van siempre al mismo sitio: la cabecera del
    archivo y la constancia de filtros aplicados.
    """

    periodos: list[str]
    facultades: list[str]
    carreras: list[str]

    def resumir(self, etiqueta: str, valores: list[str]) -> str | None:
        """Un nombre si es uno, «N etiqueta» si son varios, nada si no hay."""
        if not valores:
            return None
        return valores[0] if len(valores) == 1 else f"{len(valores)} {etiqueta}"


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
    periodos: list[str] = field(default_factory=list)
    facultades: list[str] = field(default_factory=list)
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


@dataclass(frozen=True, slots=True)
class EntradaCarrerasDisponibles:
    """De que periodos y facultades se quieren las carreras."""

    pao_ids: tuple[UUID, ...] = ()
    facultad_ids: tuple[UUID, ...] = ()


class CarrerasDisponibles(CasoDeUso[EntradaCarrerasDisponibles, list[ElementoCatalogo]]):
    """Carreras que existen en los periodos y facultades elegidos.

    La pantalla de exportacion la usa para acotar su lista: con 278 carreras,
    ofrecerlas todas cuando se marco una facultad convierte el selector en un
    campo de busqueda a ciegas.
    """

    nombre = "reportes.carreras_disponibles"
    descripcion = "Carreras presentes en los periodos y facultades indicados"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaCarrerasDisponibles, contexto: ContextoEjecucion
    ) -> list[ElementoCatalogo]:
        async with self._uow:
            return await self._uow.distributivo.carreras_presentes(
                FiltroDistributivo(
                    pao_ids=entrada.pao_ids,
                    facultad_ids=entrada.facultad_ids,
                    alcance=contexto.alcance,
                )
            )


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
        self,
        entrada: EntradaReporteDistributivo,
        contexto: ContextoEjecucion,
        *,
        limite: int | None,
    ) -> tuple[PlantillaDistributivo, ContenidoPlantilla, _Seleccion]:
        plantilla = self._plantillas.obtener(entrada.plantilla)

        if not entrada.pao_ids:
            raise ErrorValidacion("Seleccione al menos un periodo academico.", campo="pao_ids")

        async with self._uow:
            periodos = await self._nombres(TipoCatalogo.PAO, entrada.pao_ids)
            facultades = await self._nombres(TipoCatalogo.FACULTAD, entrada.facultad_ids)
            carreras = await self._nombres(TipoCatalogo.CARRERA, entrada.carrera_ids)

            contenido = await plantilla.construir(
                self._uow,
                FiltroDistributivo(
                    pao_ids=entrada.pao_ids,
                    facultad_ids=entrada.facultad_ids,
                    carrera_ids=entrada.carrera_ids,
                    # Quien coordina una facultad exporta su facultad, no el
                    # padron entero, aunque pida «todas».
                    alcance=contexto.alcance,
                ),
                incluir_auditoria=entrada.incluir_columnas_auditoria,
                limite=limite,
            )

        return plantilla, contenido, _Seleccion(periodos, facultades, carreras)

    async def _nombres(self, tipo: TipoCatalogo, ids: tuple[UUID, ...]) -> list[str]:
        """Resuelve los identificadores a texto, fallando si alguno no existe.

        Se comprueba uno a uno en lugar de dejar que la consulta devuelva menos
        filas: un identificador equivocado daria un reporte incompleto sin que
        nadie se enterara.
        """
        nombres: list[str] = []
        for elemento_id in ids:
            elemento = await self._uow.catalogos.obtener(tipo, elemento_id)
            if elemento is None:
                raise NoEncontrado(tipo.singular, elemento_id)
            nombres.append(elemento.nombre)
        return nombres


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
        plantilla, contenido, seleccion = await self._resolver(
            entrada, contexto, limite=_FILAS_VISTA_PREVIA
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
            periodos=seleccion.periodos,
            facultades=seleccion.facultades,
            carreras=seleccion.carreras,
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
        plantilla, contenido, seleccion = await self._resolver(entrada, contexto, limite=None)

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
            subtitulo=self._subtitulo(seleccion),
            columnas=contenido.columnas,
            filas=contenido.filas,
            filtros_aplicados=self._filtros(plantilla, seleccion),
            generado_en=self._reloj.ahora(),
            generado_por=contexto.actor.nombre_completo if contexto.actor else "Sistema",
            totales=contenido.totales,
            solo_datos=plantilla.solo_datos,
        )
        return self._exportadores.obtener(entrada.formato).exportar(tabla)

    # ------------------------------------------------------------ internos
    @staticmethod
    def _subtitulo(seleccion: _Seleccion) -> str:
        """Cabecera corta: un nombre si se eligio uno, un recuento si varios."""
        partes = [
            seleccion.resumir("periodos", seleccion.periodos),
            seleccion.resumir("facultades", seleccion.facultades),
            seleccion.resumir("carreras", seleccion.carreras),
        ]
        return " · ".join(p for p in partes if p)

    @staticmethod
    def _filtros(plantilla: PlantillaDistributivo, seleccion: _Seleccion) -> dict[str, object]:
        """Constancia de lo aplicado, **enumerado**.

        Se listan por nombre y no por cantidad: un reporte que no deja
        constancia de que periodos y carreras incluye no se puede contrastar
        con otro, que es justo para lo que se emite.
        """
        filtros: dict[str, object] = {"Plantilla": plantilla.nombre}
        for etiqueta, valores in (
            ("Periodos", seleccion.periodos),
            ("Facultades", seleccion.facultades),
            ("Carreras", seleccion.carreras),
        ):
            if valores:
                filtros[etiqueta] = "; ".join(valores)
        return filtros
