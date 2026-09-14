"""Esquemas de entrada y salida del distributivo docente."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, field_validator

from app.api.esquemas.comunes import EsquemaBase
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente
from app.domain.ports.distributivo import FilaDistributivoResuelta, ResumenDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.value_objects_distributivo import DistribucionHoras, Identificacion

# ===========================================================================
# Catalogos
# ===========================================================================


class ElementoCatalogoSalida(EsquemaBase):
    id: UUID
    tipo: TipoCatalogo
    codigo: str
    nombre: str
    descripcion: str
    activo: bool
    orden: int
    codigo_erp: str
    atributos: dict[str, Any]
    creado_en: datetime
    actualizado_en: datetime

    @classmethod
    def desde(cls, e: ElementoCatalogo) -> ElementoCatalogoSalida:
        return cls(
            id=e.id,
            tipo=e.tipo,
            codigo=e.codigo,
            nombre=e.nombre,
            descripcion=e.descripcion,
            activo=e.activo,
            orden=e.orden,
            codigo_erp=e.codigo_erp,
            atributos=e.atributos,
            creado_en=e.creado_en,
            actualizado_en=e.actualizado_en,
        )


class OpcionSelector(EsquemaBase):
    """Forma minima para poblar un desplegable.

    Se devuelve esto y no el elemento completo: un selector con 278 carreras no
    necesita las marcas de auditoria de cada una.
    """

    id: UUID
    codigo: str
    nombre: str

    @classmethod
    def desde(cls, e: ElementoCatalogo) -> OpcionSelector:
        return cls(id=e.id, codigo=e.codigo, nombre=e.nombre)


class ElementoCatalogoCrear(EsquemaBase):
    codigo: Annotated[str, Field(min_length=1, max_length=320)]
    nombre: Annotated[str, Field(min_length=1, max_length=320)]
    descripcion: str = ""
    activo: bool = True
    orden: int = 0
    codigo_erp: Annotated[str, Field(max_length=64)] = ""
    atributos: dict[str, Any] = Field(default_factory=dict)


class ElementoCatalogoActualizar(EsquemaBase):
    nombre: str | None = Field(default=None, max_length=320)
    descripcion: str | None = None
    activo: bool | None = None
    orden: int | None = None
    codigo_erp: str | None = Field(default=None, max_length=64)
    atributos: dict[str, Any] | None = None


class TipoCatalogoSalida(EsquemaBase):
    tipo: str
    etiqueta: str
    singular: str


# ===========================================================================
# Docentes
# ===========================================================================


class DocenteSalida(EsquemaBase):
    id: UUID
    identificacion: str
    es_cedula: bool
    nombre_completo: str
    genero_id: UUID | None
    persona_id: UUID | None
    titulos_ids: list[UUID]
    activo: bool
    observaciones: str | None
    creado_en: datetime

    @classmethod
    def desde(cls, d: Docente) -> DocenteSalida:
        return cls(
            id=d.id,
            identificacion=d.identificacion.valor,
            es_cedula=d.identificacion.es_cedula,
            nombre_completo=d.nombre_completo,
            genero_id=d.genero_id,
            persona_id=d.persona_id,
            titulos_ids=list(d.titulos_ids),
            activo=d.activo,
            observaciones=d.observaciones,
            creado_en=d.creado_en,
        )


class DocenteDetalleSalida(EsquemaBase):
    docente: DocenteSalida
    titulos: list[ElementoCatalogoSalida]
    total_filas: int


class DocenteCrear(EsquemaBase):
    identificacion: Annotated[str, Field(min_length=5, max_length=20)]
    nombre_completo: Annotated[str, Field(min_length=3, max_length=200)]
    genero_id: UUID | None = None
    titulos_ids: list[UUID] = Field(default_factory=list)
    observaciones: str | None = None

    @field_validator("identificacion")
    @classmethod
    def _validar(cls, valor: str) -> str:
        """Valida en el borde para devolver un 422 con el campo exacto.

        Admite cedula o pasaporte: el padron docente incluye extranjeros.
        """
        return Identificacion(valor).valor


class DocenteActualizar(EsquemaBase):
    nombre_completo: str | None = Field(default=None, max_length=200)
    genero_id: UUID | None = None
    titulos_ids: list[UUID] | None = None
    activo: bool | None = None
    observaciones: str | None = None


# ===========================================================================
# Distributivo
# ===========================================================================


class HorasSalida(EsquemaBase):
    """Detalle de horas por bloque, con sus totales."""

    docencia: dict[str, float]
    gestion: dict[str, float]
    investigacion: dict[str, float]
    vinculacion: dict[str, float]
    total_docencia: float
    total_gestion: float
    total_investigacion: float
    total_vinculacion: float
    total: float

    @classmethod
    def desde(cls, h: DistribucionHoras) -> HorasSalida:
        return cls(
            docencia=h.docencia,
            gestion=h.gestion,
            investigacion=h.investigacion,
            vinculacion=h.vinculacion,
            total_docencia=h.total_docencia,
            total_gestion=h.total_gestion,
            total_investigacion=h.total_investigacion,
            total_vinculacion=h.total_vinculacion,
            total=h.total,
        )


class FilaDistributivoSalida(EsquemaBase):
    """Fila con los catalogos ya resueltos a texto, lista para la tabla."""

    id: UUID
    docente_id: UUID
    docente_identificacion: str
    docente_nombre: str

    pao_id: UUID
    pao: str
    facultad_id: UUID
    facultad: str
    carrera_id: UUID
    carrera: str

    sede_id: UUID | None
    sede: str | None
    nivel_id: UUID | None
    nivel: str | None
    titularidad_id: UUID | None
    titularidad: str | None
    dedicacion_id: UUID | None
    dedicacion: str | None
    categoria_id: UUID | None
    categoria: str | None
    tipo_titulo_id: UUID | None
    tipo_titulo: str | None

    asignaturas_ids: list[UUID]
    asignaturas: list[str]
    requiere_asignatura: bool
    horas: HorasSalida
    total_horas: float
    medida: str | None
    observaciones: str | None
    actualizado_en: datetime

    @classmethod
    def desde(cls, r: FilaDistributivoResuelta) -> FilaDistributivoSalida:
        f = r.fila
        return cls(
            id=f.id,
            docente_id=f.docente_id,
            docente_identificacion=r.docente_identificacion,
            docente_nombre=r.docente_nombre,
            pao_id=f.pao_id,
            pao=r.pao,
            facultad_id=f.facultad_id,
            facultad=r.facultad,
            carrera_id=f.carrera_id,
            carrera=r.carrera,
            sede_id=f.sede_id,
            sede=r.sede,
            nivel_id=f.nivel_id,
            nivel=r.nivel,
            titularidad_id=f.titularidad_id,
            titularidad=r.titularidad,
            dedicacion_id=f.dedicacion_id,
            dedicacion=r.dedicacion,
            categoria_id=f.categoria_id,
            categoria=r.categoria,
            tipo_titulo_id=f.tipo_titulo_id,
            tipo_titulo=r.tipo_titulo,
            asignaturas_ids=list(f.asignaturas_ids),
            asignaturas=list(r.asignaturas),
            requiere_asignatura=f.requiere_asignatura,
            horas=HorasSalida.desde(f.horas),
            total_horas=f.total_horas,
            medida=f.medida,
            observaciones=f.observaciones,
            actualizado_en=f.actualizado_en,
        )


class FilaDistributivoCrear(EsquemaBase):
    docente_id: UUID
    pao_id: UUID
    facultad_id: UUID
    carrera_id: UUID
    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None
    asignaturas_ids: list[UUID] = Field(default_factory=list)
    horas: dict[str, float] = Field(
        default_factory=dict,
        description="Horas por subactividad: Da..Dn, Ga..Gn, Ia..Ij, Va..Vi",
    )
    medida: str | None = None
    observaciones: str | None = None


class FilaDistributivoActualizar(EsquemaBase):
    facultad_id: UUID | None = None
    carrera_id: UUID | None = None
    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None
    asignaturas_ids: list[UUID] | None = None
    horas: dict[str, float] | None = None
    medida: str | None = None
    observaciones: str | None = None


class ResumenDistributivoSalida(EsquemaBase):
    total_filas: int
    total_docentes: int
    total_horas: float
    filas_sin_asignatura: int
    por_categoria: list[dict[str, Any]]
    por_dedicacion: list[dict[str, Any]]
    por_facultad: list[dict[str, Any]]

    @classmethod
    def desde(cls, r: ResumenDistributivo) -> ResumenDistributivoSalida:
        def pares(datos: list[tuple[str, int]]) -> list[dict[str, Any]]:
            return [{"etiqueta": e, "valor": v} for e, v in datos]

        return cls(
            total_filas=r.total_filas,
            total_docentes=r.total_docentes,
            total_horas=r.total_horas,
            filas_sin_asignatura=r.filas_sin_asignatura,
            por_categoria=pares(r.por_categoria),
            por_dedicacion=pares(r.por_dedicacion),
            por_facultad=pares(r.por_facultad),
        )


# ===========================================================================
# Reporte
# ===========================================================================


class AsignaturaCapturada(EsquemaBase):
    """La asignatura que se registra para una fila."""

    fila_id: UUID
    asignatura: str = Field(
        default="",
        # Varias materias en una sola cadena: 400 se quedaba corto en cuanto
        # una fila tiene tres o cuatro.
        max_length=800,
        description=(
            "Una o varias asignaturas separadas por comas. Se resuelven contra el "
            "catalogo y se agregan las que no existan. Texto vacio las retira."
        ),
    )


class PeticionCapturaAsignaturas(EsquemaBase):
    filas: list[AsignaturaCapturada] = Field(min_length=1, max_length=500)


class ResultadoCapturaAsignaturasSalida(EsquemaBase):
    actualizadas: int
    sin_cambios: int
    asignaturas_creadas: int = 0


class PeticionReporteDistributivo(EsquemaBase):
    """Filtros de la exportacion.

    Los tres admiten varios valores: un reporte rara vez es de un periodo y una
    carrera. Se emite una facultad con todos sus programas, o la evolucion de
    una carrera a lo largo de varios periodos.
    """

    pao_ids: list[UUID] = Field(min_length=1, description="Al menos un periodo academico")
    facultad_ids: list[UUID] = Field(default_factory=list)
    carrera_ids: list[UUID] = Field(default_factory=list)
    plantilla: str | None = Field(
        default=None,
        description="Codigo de la plantilla de exportacion. Vacio usa la institucional.",
    )
    incluir_columnas_auditoria: bool = False


class PlantillaReporteSalida(EsquemaBase):
    """Una plantilla de exportacion disponible."""

    codigo: str
    nombre: str
    descripcion: str
    admite_auditoria: bool


class ColumnaReporteSalida(EsquemaBase):
    """Definicion de una columna, para que la interfaz pinte la vista previa.

    Las columnas viajan con la respuesta en lugar de estar fijas en el frontend:
    es lo que permite agregar plantillas sin tocar la interfaz.
    """

    clave: str
    titulo: str
    ancho: int
    tipo: str
    alineacion: str
    color_cabecera: str | None

    @classmethod
    def desde(cls, c: ColumnaReporte) -> ColumnaReporteSalida:
        return cls(
            clave=c.clave,
            titulo=c.titulo,
            ancho=c.ancho,
            tipo=c.tipo,
            alineacion=c.alineacion,
            color_cabecera=c.color_cabecera,
        )


class VistaPreviaReporteSalida(EsquemaBase):
    plantilla: str
    nombre_plantilla: str
    columnas: list[ColumnaReporteSalida]

    #: Valores en el orden de `columnas`, no un objeto por fila: las claves del
    #: consolidado —`APELLIDOS.Y.NOMBRES`, `N.x`— no sobreviven la conversion a
    #: camelCase que hace el cliente con los nombres de campo.
    filas: list[list[Any]]
    total_filas: int
    total_docentes: int
    sin_asignatura: int
    sin_anio_inicio: int
    periodos: list[str]
    facultades: list[str]
    carreras: list[str]
    esta_completo: bool


# ===========================================================================
# Importacion
# ===========================================================================


class ResultadoImportacionSalida(EsquemaBase):
    total_filas_leidas: int
    filas_creadas: int
    docentes_creados: int
    docentes_existentes: int
    filas_consolidadas: int
    titulos_creados: int
    elementos_catalogo_creados: dict[str, int]
    rechazadas: list[dict[str, Any]]
    consolidaciones: list[dict[str, Any]]
    exitosa: bool
    resumen: str
