"""Esquemas de autenticacion y perfil."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr, Field

from app.api.esquemas.comunes import EsquemaBase
from app.application.casos_uso.autenticacion import PerfilUsuario, SesionIniciada
from app.domain.entities.auth import Rol, Usuario
from app.domain.enums import AuthProvider


class PeticionInicioSesion(EsquemaBase):
    email: EmailStr = Field(description="Correo institucional")
    contrasena: Annotated[str, Field(min_length=1, max_length=128)]


class PeticionInicioLDAP(EsquemaBase):
    usuario: Annotated[str, Field(min_length=1, max_length=100)] = Field(
        description="Nombre de usuario del directorio activo"
    )
    contrasena: Annotated[str, Field(min_length=1, max_length=128)]


class PeticionRefresco(EsquemaBase):
    token_refresco: Annotated[str, Field(min_length=10)]


class PeticionCambioContrasena(EsquemaBase):
    contrasena_actual: Annotated[str, Field(min_length=1, max_length=128)]
    contrasena_nueva: Annotated[str, Field(min_length=10, max_length=128)]


class RolResumen(EsquemaBase):
    codigo: str
    nombre: str
    descripcion: str = ""
    es_sistema: bool = False

    @classmethod
    def desde(cls, rol: Rol) -> RolResumen:
        return cls(
            codigo=rol.codigo,
            nombre=rol.nombre,
            descripcion=rol.descripcion,
            es_sistema=rol.es_sistema,
        )


class UsuarioSalida(EsquemaBase):
    id: UUID
    email: str
    nombre_completo: str
    proveedor: AuthProvider
    activo: bool
    es_superusuario: bool
    debe_cambiar_contrasena: bool
    roles: list[RolResumen]
    permisos: list[str] = Field(
        description="Permisos efectivos: la union de los de todos sus roles"
    )
    ultimo_acceso: datetime | None = None
    creado_en: datetime

    @classmethod
    def desde(cls, usuario: Usuario) -> UsuarioSalida:
        return cls(
            id=usuario.id,
            email=usuario.email.valor,
            nombre_completo=usuario.nombre_completo,
            proveedor=usuario.proveedor,
            activo=usuario.activo,
            es_superusuario=usuario.es_superusuario,
            debe_cambiar_contrasena=usuario.debe_cambiar_contrasena,
            roles=sorted((RolResumen.desde(r) for r in usuario.roles), key=lambda r: r.codigo),
            permisos=sorted(p.value for p in usuario.permisos),
            ultimo_acceso=usuario.ultimo_acceso,
            creado_en=usuario.creado_en,
        )


class TokensSalida(EsquemaBase):
    acceso: str
    refresco: str
    tipo: str = "bearer"
    expira_en_segundos: int


class SesionSalida(EsquemaBase):
    tokens: TokensSalida
    usuario: UsuarioSalida
    debe_cambiar_contrasena: bool = False

    @classmethod
    def desde(cls, sesion: SesionIniciada) -> SesionSalida:
        return cls(
            tokens=TokensSalida(
                acceso=sesion.tokens.acceso,
                refresco=sesion.tokens.refresco,
                tipo=sesion.tokens.tipo,
                expira_en_segundos=sesion.tokens.expira_en_segundos,
            ),
            usuario=UsuarioSalida.desde(sesion.usuario),
            debe_cambiar_contrasena=sesion.debe_cambiar_contrasena,
        )


class PerfilSalida(EsquemaBase):
    usuario: UsuarioSalida
    permisos: list[str]

    @classmethod
    def desde(cls, perfil: PerfilUsuario) -> PerfilSalida:
        return cls(usuario=UsuarioSalida.desde(perfil.usuario), permisos=perfil.permisos)


class MetodosAccesoSalida(EsquemaBase):
    """Metodos de acceso habilitados.

    El frontend consulta este endpoint sin autenticarse para decidir que botones
    mostrar en la pantalla de acceso, en lugar de llevar la configuracion
    duplicada en su propio build.
    """

    local: bool = True
    google: bool = False
    ldap: bool = False
    url_google: str | None = None
