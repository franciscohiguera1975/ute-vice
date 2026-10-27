"""Modelos ORM de la matricula estudiantil.

Tres tablas: `estudiantes` (el padron de personas), `matriculas_estudiante`
(una fila por carrera y periodo en que un estudiante esta matriculado) y
`becas_estudiante` (el detalle de becas o descuentos de cada matricula, una
fila por beca individual).

Alimentan al futuro Tablero Docente, que calculara la relacion
estudiantes/docente por carrera. Este modulo solo carga y almacena: ese
calculo lo construye otra persona sobre
`app.domain.ports.estudiantes.RepositorioEstudiantes.conteo_por_carrera`.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, MixinAuditoria


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )


class EstudianteModel(Base, MixinAuditoria):
    """Una persona del padron de matricula.

    `cedula` **no lleva `UniqueConstraint`**: a diferencia de `docentes`,
    Banner puede repetir la misma cedula en dos matriculas del mismo periodo
    -doble carrera o sede-, y el importador no impone una identidad unica que
    el origen no garantiza.
    """

    __tablename__ = "estudiantes"
    __table_args__ = (Index("ix_estudiantes_cedula", "cedula"),)

    id: Mapped[UUID] = _uuid_pk()

    cedula: Mapped[str] = mapped_column(String(20), nullable=False)
    id_banner: Mapped[str | None] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)

    genero_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_generos.id", ondelete="SET NULL")
    )

    mail_personal: Mapped[str | None] = mapped_column(String(200))
    mail_ute: Mapped[str | None] = mapped_column(String(200))
    telefono_celular: Mapped[str | None] = mapped_column(String(32))
    telefono_fijo: Mapped[str | None] = mapped_column(String(32))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)

    matriculas: Mapped[list[MatriculaEstudianteModel]] = relationship(
        back_populates="estudiante", cascade="all, delete-orphan", lazy="noload"
    )


class MatriculaEstudianteModel(Base, MixinAuditoria):
    """Un estudiante matriculado en una carrera durante un periodo de Banner.

    `periodo` es el codigo de seis digitos que trae Banner, sin relacion con
    `cat_paos` del distributivo docente -ver la nota de modulo en
    `app.domain.entities.estudiantes`-.

    `(estudiante_id, periodo, carrera, sede)` es la clave natural: Banner
    permite doble matricula el mismo periodo cuando la carrera o la sede
    difieren. `postgresql_nulls_not_distinct` evita que dos matriculas sin
    sede del mismo estudiante y periodo se traten como distintas solo por
    tener la sede en blanco.
    """

    __tablename__ = "matriculas_estudiante"
    __table_args__ = (
        UniqueConstraint(
            "estudiante_id",
            "periodo",
            "carrera",
            "sede",
            name="uq_matriculas_estudiante_natural",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_matriculas_estudiante_periodo", "periodo"),
        Index("ix_matriculas_estudiante_carrera", "carrera_id"),
    )

    id: Mapped[UUID] = _uuid_pk()

    estudiante_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("estudiantes.id", ondelete="CASCADE"), nullable=False
    )

    periodo: Mapped[str] = mapped_column(String(6), nullable=False)

    #: Texto crudo del Excel, tal como lo trae Banner.
    sede: Mapped[str | None] = mapped_column(String(100))
    facultad: Mapped[str | None] = mapped_column(String(200))
    carrera: Mapped[str | None] = mapped_column(String(255))

    #: Resolucion contra `cat_carreras` por igualdad exacta de nombre.
    #: `None` cuando no hubo coincidencia: ver
    #: `app.application.casos_uso.importar_estudiantes.ImportarEstudiantes`.
    carrera_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cat_carreras.id", ondelete="SET NULL")
    )

    tipo_carrera: Mapped[str | None] = mapped_column(String(64))
    modalidad: Mapped[str | None] = mapped_column(String(64))
    nivel_formacion_1: Mapped[str | None] = mapped_column(String(64))
    nivel_formacion_2: Mapped[str | None] = mapped_column(String(100))

    tipo_estudiante: Mapped[str | None] = mapped_column(String(32))
    sistema: Mapped[str | None] = mapped_column(String(32))
    matriculado: Mapped[str | None] = mapped_column(String(32))
    solicitud_retiro: Mapped[str | None] = mapped_column(Text)
    bloqueo_plataforma: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estado: Mapped[str | None] = mapped_column(String(16))

    estudiante: Mapped[EstudianteModel] = relationship(back_populates="matriculas", lazy="noload")
    becas: Mapped[list[BecaEstudianteModel]] = relationship(
        back_populates="matricula", cascade="all, delete-orphan", lazy="noload"
    )


class BecaEstudianteModel(Base, MixinAuditoria):
    """Una beca o descuento individual de una matricula.

    Una fila por beca: el origen puede traer varias en una misma celda -beca
    deportiva y descuento por hermano a la vez-, separadas por coma. Ver
    `app.infrastructure.importadores.estudiantes_excel._becas`.
    """

    __tablename__ = "becas_estudiante"
    __table_args__ = (Index("ix_becas_estudiante_matricula", "matricula_id"),)

    id: Mapped[UUID] = _uuid_pk()

    matricula_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("matriculas_estudiante.id", ondelete="CASCADE"),
        nullable=False,
    )

    codigo_beca: Mapped[str | None] = mapped_column(String(32))
    financiamiento: Mapped[str | None] = mapped_column(String(32))
    tipo_beca: Mapped[str | None] = mapped_column(String(100))
    porcentaje: Mapped[float | None] = mapped_column(Float)

    matricula: Mapped[MatriculaEstudianteModel] = relationship(
        back_populates="becas", lazy="noload"
    )
