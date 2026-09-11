"""Entidades del dominio."""

from app.domain.entities.auth import PermisoEntidad, Rol, TokenRefresco, Usuario
from app.domain.entities.consulta import (
    CambioDetectado,
    ConsultaLog,
    ItemJob,
    JobCobertura,
)
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo

__all__ = [
    "CambioDetectado",
    "ConsultaLog",
    "ItemJob",
    "JobCobertura",
    "PermisoEntidad",
    "Persona",
    "Rol",
    "Titulo",
    "TokenRefresco",
    "Usuario",
]
