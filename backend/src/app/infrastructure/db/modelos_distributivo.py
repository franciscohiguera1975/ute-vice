"""Modelos ORM del distributivo docente.

Doce tablas de catalogo con el prefijo `cat_`, mas `docentes`, `distributivo` y
la relacion `docente_titulos`.

El prefijo no es decorativo: hace visible en el esquema que son catalogos, y
evita el choque entre el catalogo de titulos profesionales del profesorado y la
tabla `titulos` del expediente academico, que son cosas distintas.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.catalogo import TipoCatalogo
from app.infrastructure.db.base import Base, MixinAuditoria


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )


class MixinCatalogo(MixinAuditoria):
    """Columnas comunes a los doce catalogos.

    `codigo` es la identidad del elemento dentro de su catalogo y es unico.
    `clave_busqueda` guarda el texto normalizado sin acentos, con indice de
    trigramas, para que buscar «pedagogia» encuentre «PEDAGOGÍA».
    """

    id: Mapped[UUID] = _uuid_pk()
    # 320 y no 160: los titulos profesionales del consolidado llegan a 300
    # caracteres una vez separados, y son el catalogo con los textos mas largos.
    codigo: Mapped[str] = mapped_column(String(320), nullable=False)
    nombre: Mapped[str] = mapped_column(String(320), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    clave_busqueda: Mapped[str] = mapped_column(Text, default="", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    #: Datos propios de cada catalogo: `anio`/`periodo` en PAO, `modalidad` en
    #: carrera, `alias` en sede. Van en JSONB en lugar de multiplicar columnas
    #: que estarian vacias en once de los doce catalogos.
    atributos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


def _indices_catalogo(tabla: str) -> tuple[Any, ...]:
    return (
        UniqueConstraint("codigo", name=f"uq_{tabla}_codigo"),
        Index(
            f"ix_{tabla}_busqueda",
            "clave_busqueda",
            postgresql_using="gin",
            postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
        ),
        Index(f"ix_{tabla}_activo_orden", "activo", "orden"),
    )


# ===========================================================================
# Los doce catalogos
# ===========================================================================


class PaoModel(Base, MixinCatalogo):
    __tablename__ = "cat_paos"
    __table_args__ = _indices_catalogo("cat_paos")


class FacultadModel(Base, MixinCatalogo):
    __tablename__ = "cat_facultades"
    __table_args__ = _indices_catalogo("cat_facultades")


class CarreraModel(Base, MixinCatalogo):
    __tablename__ = "cat_carreras"
    __table_args__ = _indices_catalogo("cat_carreras")


class SedeModel(Base, MixinCatalogo):
    __tablename__ = "cat_sedes"
    __table_args__ = _indices_catalogo("cat_sedes")


class TitularidadModel(Base, MixinCatalogo):
    __tablename__ = "cat_titularidades"
    __table_args__ = _indices_catalogo("cat_titularidades")


class DedicacionModel(Base, MixinCatalogo):
    __tablename__ = "cat_dedicaciones"
    __table_args__ = _indices_catalogo("cat_dedicaciones")


class CategoriaModel(Base, MixinCatalogo):
    __tablename__ = "cat_categorias"
    __table_args__ = _indices_catalogo("cat_categorias")


class NivelModel(Base, MixinCatalogo):
    __tablename__ = "cat_niveles"
    __table_args__ = _indices_catalogo("cat_niveles")


class ProgramaModel(Base, MixinCatalogo):
    __tablename__ = "cat_programas"
    __table_args__ = _indices_catalogo("cat_programas")


class TituloProfesionalModel(Base, MixinCatalogo):
    __tablename__ = "cat_titulos_profesionales"
    __table_args__ = _indices_catalogo("cat_titulos_profesionales")


class TipoTituloModel(Base, MixinCatalogo):
    __tablename__ = "cat_tipos_titulo"
    __table_args__ = _indices_catalogo("cat_tipos_titulo")


class GeneroModel(Base, MixinCatalogo):
    __tablename__ = "cat_generos"
    __table_args__ = _indices_catalogo("cat_generos")


#: Traduccion entre el tipo de catalogo del dominio y su tabla. Es lo que hace
#: posible que un solo repositorio sirva a los doce.
MODELOS_CATALOGO: dict[TipoCatalogo, type[Base]] = {
    TipoCatalogo.PAO: PaoModel,
    TipoCatalogo.FACULTAD: FacultadModel,
    TipoCatalogo.CARRERA: CarreraModel,
    TipoCatalogo.SEDE: SedeModel,
    TipoCatalogo.TITULARIDAD: TitularidadModel,
    TipoCatalogo.DEDICACION: DedicacionModel,
    TipoCatalogo.CATEGORIA: CategoriaModel,
    TipoCatalogo.NIVEL: NivelModel,
    TipoCatalogo.PROGRAMA: ProgramaModel,
    TipoCatalogo.TITULO_PROFESIONAL: TituloProfesionalModel,
    TipoCatalogo.TIPO_TITULO: TipoTituloModel,
    TipoCatalogo.GENERO: GeneroModel,
}


# ===========================================================================
# Docentes
# ===========================================================================

# ---------------------------------------------------------------------------
# Alcance academico de un usuario
# ---------------------------------------------------------------------------
# Viven aqui y no junto a `usuarios` porque apuntan a los catalogos: es este
# modulo el que los define. Se leen con consultas explicitas en lugar de con
# una relacion del ORM, para no arrastrar carga diferida hasta la resolucion
# de permisos, que ocurre en cada peticion.


def _tabla_alcance(nombre: str, columna: str, catalogo: str) -> Table:
    """Las dos tablas de alcance son identicas salvo a que catalogo apuntan."""
    return Table(
        nombre,
        Base.metadata,
        Column(
            "usuario_id",
            PgUUID(as_uuid=True),
            ForeignKey("usuarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        Column(
            columna,
            PgUUID(as_uuid=True),
            ForeignKey(f"{catalogo}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


usuario_facultades = _tabla_alcance("usuario_facultades", "facultad_id", "cat_facultades")
usuario_carreras = _tabla_alcance("usuario_carreras", "carrera_id", "cat_carreras")


docente_titulos = Table(
    "docente_titulos",
    Base.metadata,
    Column(
        "docente_id",
        PgUUID(as_uuid=True),
        ForeignKey("docentes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "titulo_id",
        PgUUID(as_uuid=True),
        ForeignKey("cat_titulos_profesionales.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("orden", Integer, nullable=False, default=0),
)


class DocenteModel(Base, MixinAuditoria):
    __tablename__ = "docentes"
    __table_args__ = (
        UniqueConstraint("identificacion", name="uq_docentes_identificacion"),
        Index(
            "ix_docentes_busqueda",
            "clave_busqueda",
            postgresql_using="gin",
            postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
        ),
        Index("ix_docentes_activo", "activo"),
    )

    id: Mapped[UUID] = _uuid_pk()

    #: Cedula o pasaporte. A diferencia de `personas.cedula`, admite documentos
    #: extranjeros: cerca del 5% del padron son docentes con pasaporte.
    identificacion: Mapped[str] = mapped_column(String(20), nullable=False)
    es_cedula: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    clave_busqueda: Mapped[str] = mapped_column(Text, default="", nullable=False)

    genero_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_generos.id", ondelete="SET NULL")
    )

    #: Enlace opcional con el expediente academico. Solo existe cuando el
    #: documento es una cedula y esa persona ya esta en el padron de `personas`.
    persona_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text)

    titulos: Mapped[list[TituloProfesionalModel]] = relationship(
        secondary=docente_titulos,
        lazy="selectin",
        order_by=docente_titulos.c.orden,
    )
    filas: Mapped[list[FilaDistributivoModel]] = relationship(
        back_populates="docente", cascade="all, delete-orphan", lazy="noload"
    )


# ===========================================================================
# Distributivo
# ===========================================================================


class FilaDistributivoModel(Base, MixinAuditoria):
    """Carga de un docente en una carrera durante un periodo academico."""

    __tablename__ = "distributivo"
    __table_args__ = (
        # `(docente, periodo, carrera, sede)` es la clave natural. La sede
        # forma parte de ella porque un mismo docente si dicta la misma carrera
        # en dos campus el mismo periodo: en el consolidado historico eso ocurre
        # en 118 casos, y sin la sede se leerian como duplicados.
        #
        # `NULLS NOT DISTINCT` es necesario: 19 filas del origen no traen sede, y
        # con el comportamiento por defecto de PostgreSQL dos nulos se consideran
        # distintos, lo que dejaria pasar duplicados reales por esa rendija.
        UniqueConstraint(
            "docente_id",
            "pao_id",
            "carrera_id",
            "sede_id",
            name="uq_distributivo_docente_pao_carrera_sede",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("total_horas >= 0", name="total_horas_no_negativo"),
        Index("ix_distributivo_pao_facultad", "pao_id", "facultad_id"),
        Index("ix_distributivo_pao_carrera", "pao_id", "carrera_id"),
        Index("ix_distributivo_docente_pao", "docente_id", "pao_id"),
        Index("ix_distributivo_carrera", "carrera_id"),
    )

    id: Mapped[UUID] = _uuid_pk()

    docente_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False
    )
    pao_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_paos.id", ondelete="RESTRICT"), nullable=False
    )
    facultad_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cat_facultades.id", ondelete="RESTRICT"),
        nullable=False,
    )
    carrera_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cat_carreras.id", ondelete="RESTRICT"),
        nullable=False,
    )

    programa_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_programas.id", ondelete="SET NULL")
    )
    sede_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_sedes.id", ondelete="SET NULL")
    )
    nivel_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_niveles.id", ondelete="SET NULL")
    )
    titularidad_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_titularidades.id", ondelete="SET NULL")
    )
    dedicacion_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_dedicaciones.id", ondelete="SET NULL")
    )
    categoria_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_categorias.id", ondelete="SET NULL")
    )
    tipo_titulo_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_tipos_titulo.id", ondelete="SET NULL")
    )

    #: No viene del consolidado: el distributivo reparte horas por tipo de
    #: actividad, no por materia. Se captura a mano porque el reporte
    #: institucional la exige.
    asignatura: Mapped[str | None] = mapped_column(String(400))

    #: Detalle de horas por subactividad, en cuatro bloques. Va en JSONB y no en
    #: 47 columnas: son datos del origen que hay que conservar, pero que nadie
    #: filtra ni ordena de forma individual. Los totales, que si se consultan,
    #: son columnas reales.
    horas_docencia: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    horas_gestion: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    horas_investigacion: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    horas_vinculacion: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    total_docencia: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_gestion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_investigacion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_vinculacion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_horas: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)

    medida: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)

    creado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    docente: Mapped[DocenteModel] = relationship(back_populates="filas", lazy="noload")
