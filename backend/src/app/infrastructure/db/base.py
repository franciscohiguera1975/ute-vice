"""Base declarativa de SQLAlchemy y convenciones del esquema."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Nombres deterministas para indices y restricciones. Sin esto, Alembic genera
#: nombres distintos en cada entorno y las migraciones dejan de ser reversibles.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)

    def __repr__(self) -> str:
        identificador = getattr(self, "id", None)
        return f"<{type(self).__name__} id={identificador}>"


class MixinAuditoria:
    """Marcas de tiempo gestionadas por la base de datos.

    Se usa `server_default`/`onupdate` en lugar de valores calculados en Python
    para que una escritura hecha desde psql o desde una migracion tambien quede
    fechada correctamente.
    """

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def utc_ahora() -> Any:
    """Expresion SQL para el instante actual en UTC."""
    return func.timezone("UTC", func.now())
