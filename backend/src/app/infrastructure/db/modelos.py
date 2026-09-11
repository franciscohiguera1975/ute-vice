"""Modelos ORM.

Son distintos de las entidades del dominio a proposito. Las entidades expresan
reglas de negocio; estos modelos expresan como se guardan las filas. Mezclarlos
haria que un cambio de esquema arrastrara al dominio, que es justamente lo que
la arquitectura busca evitar. La traduccion entre ambos vive en `mapeadores.py`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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


# ===========================================================================
# Identidad y acceso
# ===========================================================================

rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column(
        "rol_id", PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permiso_id",
        PgUUID(as_uuid=True),
        ForeignKey("permisos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

usuario_roles = Table(
    "usuario_roles",
    Base.metadata,
    Column(
        "usuario_id",
        PgUUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "rol_id", PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
)


class PermisoModel(Base):
    __tablename__ = "permisos"

    id: Mapped[UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    modulo: Mapped[str] = mapped_column(String(32), default="general", nullable=False, index=True)

    roles: Mapped[list[RolModel]] = relationship(
        secondary=rol_permisos, back_populates="permisos", lazy="selectin"
    )


class RolModel(Base, MixinAuditoria):
    __tablename__ = "roles"

    id: Mapped[UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(64), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permisos: Mapped[list[PermisoModel]] = relationship(
        secondary=rol_permisos, back_populates="roles", lazy="selectin"
    )
    usuarios: Mapped[list[UsuarioModel]] = relationship(
        secondary=usuario_roles, back_populates="roles", lazy="noload"
    )


class UsuarioModel(Base, MixinAuditoria):
    __tablename__ = "usuarios"
    __table_args__ = (
        # Una cuenta local necesita hash; una federada, identificador externo.
        CheckConstraint(
            "(proveedor = 'LOCAL' AND hash_contrasena IS NOT NULL) OR "
            "(proveedor <> 'LOCAL' AND identificador_externo IS NOT NULL)",
            name="credencial_coherente_con_proveedor",
        ),
        UniqueConstraint("proveedor", "identificador_externo", name="uq_identidad_externa"),
        Index("ix_usuarios_activo", "activo"),
    )

    id: Mapped[UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    proveedor: Mapped[str] = mapped_column(String(16), default="LOCAL", nullable=False)
    hash_contrasena: Mapped[str | None] = mapped_column(String(256))
    identificador_externo: Mapped[str | None] = mapped_column(String(200))

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    es_superusuario: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    debe_cambiar_contrasena: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    intentos_fallidos: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list[RolModel]] = relationship(
        secondary=usuario_roles, back_populates="usuarios", lazy="selectin"
    )
    tokens: Mapped[list[TokenRefrescoModel]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", lazy="noload"
    )


class TokenRefrescoModel(Base):
    __tablename__ = "tokens_refresco"
    __table_args__ = (Index("ix_tokens_usuario_activos", "usuario_id", "revocado_en"),)

    id: Mapped[UUID] = _uuid_pk()
    usuario_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    hash_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reemplazado_por: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    direccion_ip: Mapped[str | None] = mapped_column(String(64))

    usuario: Mapped[UsuarioModel] = relationship(back_populates="tokens", lazy="noload")


# ===========================================================================
# Personas y titulos
# ===========================================================================


class PersonaModel(Base, MixinAuditoria):
    __tablename__ = "personas"
    __table_args__ = (
        CheckConstraint("char_length(cedula) = 10", name="cedula_diez_digitos"),
        Index(
            "ix_personas_busqueda",
            "clave_busqueda",
            postgresql_using="gin",
            postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
        ),
        Index("ix_personas_cobertura", "activo", "ultima_consulta_en"),
        Index("ix_personas_unidad", "unidad"),
    )

    id: Mapped[UUID] = _uuid_pk()
    cedula: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    tipo_documento: Mapped[str] = mapped_column(String(16), default="CEDULA", nullable=False)
    nombres: Mapped[str] = mapped_column(String(120), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(120), nullable=False)
    clave_busqueda: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """Texto normalizado sin acentos. Soporta la busqueda difusa por trigramas."""

    email_institucional: Mapped[str | None] = mapped_column(String(254), index=True)
    email_personal: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(32))

    tipo_vinculacion: Mapped[str] = mapped_column(String(24), default="OTRO", nullable=False)
    unidad: Mapped[str | None] = mapped_column(String(160))
    cargo: Mapped[str | None] = mapped_column(String(160))
    codigo_empleado: Mapped[str | None] = mapped_column(String(40), index=True)
    fecha_ingreso: Mapped[date | None] = mapped_column(Date)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text)

    ultima_consulta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ultima_consulta_estado: Mapped[str | None] = mapped_column(String(24))
    ultima_consulta_exitosa_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_consultas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titulos_registrados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    creado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    titulos: Mapped[list[TituloModel]] = relationship(
        back_populates="persona", cascade="all, delete-orphan", lazy="noload"
    )
    logs: Mapped[list[ConsultaLogModel]] = relationship(
        back_populates="persona", cascade="all, delete-orphan", lazy="noload"
    )


class TituloModel(Base, MixinAuditoria):
    __tablename__ = "titulos"
    __table_args__ = (
        # La huella identifica al titulo por contenido: impide duplicarlo para
        # la misma persona aunque el proveedor lo devuelva con otro formato.
        UniqueConstraint("persona_id", "huella", name="uq_titulo_por_persona"),
        Index("ix_titulos_nivel_estado", "nivel", "estado"),
        Index("ix_titulos_institucion", "institucion"),
        Index("ix_titulos_registro", "numero_registro"),
    )

    id: Mapped[UUID] = _uuid_pk()
    persona_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    denominacion: Mapped[str] = mapped_column(String(400), nullable=False)
    institucion: Mapped[str] = mapped_column(String(300), nullable=False)
    nivel: Mapped[str] = mapped_column(String(24), default="NO_DETERMINADO", nullable=False)
    numero_registro: Mapped[str | None] = mapped_column(String(64))
    fecha_registro: Mapped[date | None] = mapped_column(Date)
    fecha_graduacion: Mapped[date | None] = mapped_column(Date)
    area_conocimiento: Mapped[str | None] = mapped_column(String(200))
    pais: Mapped[str] = mapped_column(String(64), default="ECUADOR", nullable=False)
    observacion_registro: Mapped[str | None] = mapped_column(Text)

    origen: Mapped[str] = mapped_column(String(16), default="SENESCYT", nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="VIGENTE", nullable=False)
    huella: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    datos_crudos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    visto_primera_vez_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visto_ultima_vez_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retirado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verificado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    verificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    persona: Mapped[PersonaModel] = relationship(back_populates="titulos", lazy="noload")


# ===========================================================================
# Consultas
# ===========================================================================


class JobCoberturaModel(Base):
    __tablename__ = "consulta_jobs"
    __table_args__ = (Index("ix_jobs_estado", "estado"),)

    id: Mapped[UUID] = _uuid_pk()
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="BORRADOR", nullable=False)

    periodo_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    periodo_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    omitidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    esperando_desafio: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    fallos_consecutivos: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    pausado_automaticamente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    motivo_pausa: Mapped[str | None] = mapped_column(Text)

    proxima_ejecucion_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_actividad_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iniciado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    configuracion: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    creado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    items: Mapped[list[ItemJobModel]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="noload"
    )


class ItemJobModel(Base):
    __tablename__ = "consulta_job_items"
    __table_args__ = (
        UniqueConstraint("job_id", "persona_id", name="uq_persona_por_job"),
        # Indice del cursor: soporta la reclamacion del siguiente item listo.
        Index("ix_items_cola", "job_id", "estado", "programado_para"),
        Index("ix_items_desafio", "desafio_id"),
    )

    id: Mapped[UUID] = _uuid_pk()
    job_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("consulta_jobs.id", ondelete="CASCADE"), nullable=False
    )
    persona_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)

    estado: Mapped[str] = mapped_column(String(24), default="PENDIENTE", nullable=False)
    programado_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    ultimo_log_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ultimo_error: Mapped[str | None] = mapped_column(Text)
    desafio_id: Mapped[str | None] = mapped_column(String(128))
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[JobCoberturaModel] = relationship(back_populates="items", lazy="noload")


class ConsultaLogModel(Base):
    """Historico de consultas. Solo se inserta; nunca se actualiza ni se borra."""

    __tablename__ = "consulta_logs"
    __table_args__ = (
        Index("ix_logs_persona_fecha", "persona_id", "iniciado_en"),
        Index("ix_logs_estado_fecha", "estado", "iniciado_en"),
        Index("ix_logs_job", "job_id"),
        Index("ix_logs_ventana", "iniciado_en"),
    )

    id: Mapped[UUID] = _uuid_pk()
    persona_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    cedula: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(24), nullable=False)

    job_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("consulta_jobs.id", ondelete="SET NULL")
    )
    proveedor: Mapped[str] = mapped_column(String(32), default="desconocido", nullable=False)
    intento: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)

    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duracion_ms: Mapped[int | None] = mapped_column(Integer)

    titulos_encontrados: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    titulos_nuevos: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    titulos_actualizados: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    titulos_retirados: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    cambios: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    mensaje: Mapped[str | None] = mapped_column(Text)
    tipo_error: Mapped[str | None] = mapped_column(String(80))
    codigo_http: Mapped[int | None] = mapped_column(SmallInteger)
    respuesta_cruda: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    ejecutado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    persona: Mapped[PersonaModel] = relationship(back_populates="logs", lazy="noload")
