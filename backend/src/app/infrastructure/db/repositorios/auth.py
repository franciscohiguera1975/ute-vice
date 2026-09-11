"""Repositorios de identidad y acceso sobre PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.auth import Rol, TokenRefresco, Usuario
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.value_objects import Email, ahora_utc
from app.infrastructure.db import mapeadores as m
from app.infrastructure.db.modelos import (
    PermisoModel,
    RolModel,
    TokenRefrescoModel,
    UsuarioModel,
    usuario_roles,
)


class RepositorioUsuariosSQL:
    """Implementacion PostgreSQL del puerto `RepositorioUsuarios`."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    def _base(self) -> Select[tuple[UsuarioModel]]:
        # Los roles y sus permisos se cargan siempre: sin ellos no se puede
        # resolver autorizacion, y cargarlos despues provocaria N+1.
        return select(UsuarioModel).options(
            selectinload(UsuarioModel.roles).selectinload(RolModel.permisos)
        )

    async def obtener(self, usuario_id: UUID) -> Usuario | None:
        fila = await self._s.scalar(self._base().where(UsuarioModel.id == usuario_id))
        return m.usuario_a_dominio(fila) if fila else None

    async def obtener_por_email(self, email: Email) -> Usuario | None:
        fila = await self._s.scalar(self._base().where(UsuarioModel.email == email.valor))
        return m.usuario_a_dominio(fila) if fila else None

    async def obtener_por_externo(self, proveedor: str, identificador: str) -> Usuario | None:
        fila = await self._s.scalar(
            self._base().where(
                UsuarioModel.proveedor == proveedor,
                UsuarioModel.identificador_externo == identificador,
            )
        )
        return m.usuario_a_dominio(fila) if fila else None

    async def listar(
        self,
        paginacion: Paginacion,
        *,
        texto: str | None = None,
        activo: bool | None = None,
        rol: str | None = None,
    ) -> Pagina[Usuario]:
        consulta = self._base()
        conteo = select(func.count()).select_from(UsuarioModel)

        if texto:
            patron = f"%{texto.lower()}%"
            filtro = func.lower(UsuarioModel.nombre_completo).like(patron) | (
                func.lower(UsuarioModel.email).like(patron)
            )
            consulta = consulta.where(filtro)
            conteo = conteo.where(filtro)
        if activo is not None:
            consulta = consulta.where(UsuarioModel.activo == activo)
            conteo = conteo.where(UsuarioModel.activo == activo)
        if rol:
            sub = (
                select(usuario_roles.c.usuario_id)
                .join(RolModel, RolModel.id == usuario_roles.c.rol_id)
                .where(RolModel.codigo == rol.upper())
            )
            consulta = consulta.where(UsuarioModel.id.in_(sub))
            conteo = conteo.where(UsuarioModel.id.in_(sub))

        total = await self._s.scalar(conteo) or 0
        filas = await self._s.scalars(
            consulta.order_by(UsuarioModel.nombre_completo)
            .offset(paginacion.offset)
            .limit(paginacion.limite)
        )
        return Pagina(
            items=[m.usuario_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def agregar(self, usuario: Usuario) -> Usuario:
        modelo = m.usuario_a_modelo(usuario)
        modelo.roles = await self._modelos_de_roles(usuario.roles)
        self._s.add(modelo)
        await self._s.flush()
        return usuario

    async def actualizar(self, usuario: Usuario) -> Usuario:
        modelo = await self._s.get(
            UsuarioModel,
            usuario.id,
            options=[selectinload(UsuarioModel.roles).selectinload(RolModel.permisos)],
        )
        if modelo is None:
            raise ValueError(f"Usuario inexistente: {usuario.id}")
        m.usuario_a_modelo(usuario, modelo)
        modelo.roles = await self._modelos_de_roles(usuario.roles)
        await self._s.flush()
        return usuario

    async def eliminar(self, usuario_id: UUID) -> None:
        await self._s.execute(delete(UsuarioModel).where(UsuarioModel.id == usuario_id))

    async def existe_email(self, email: Email, *, excluyendo: UUID | None = None) -> bool:
        consulta = (
            select(func.count()).select_from(UsuarioModel).where(UsuarioModel.email == email.valor)
        )
        if excluyendo:
            consulta = consulta.where(UsuarioModel.id != excluyendo)
        return bool(await self._s.scalar(consulta))

    async def contar_superusuarios_activos(self) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(UsuarioModel)
                .where(UsuarioModel.es_superusuario.is_(True), UsuarioModel.activo.is_(True))
            )
            or 0
        )

    async def _modelos_de_roles(self, roles: set[Rol]) -> list[RolModel]:
        if not roles:
            return []
        filas = await self._s.scalars(
            select(RolModel)
            .options(selectinload(RolModel.permisos))
            .where(RolModel.codigo.in_([r.codigo for r in roles]))
        )
        return list(filas)


class RepositorioRolesSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    def _base(self) -> Select[tuple[RolModel]]:
        return select(RolModel).options(selectinload(RolModel.permisos))

    async def obtener(self, rol_id: UUID) -> Rol | None:
        fila = await self._s.scalar(self._base().where(RolModel.id == rol_id))
        return m.rol_a_dominio(fila) if fila else None

    async def obtener_por_codigo(self, codigo: str) -> Rol | None:
        fila = await self._s.scalar(self._base().where(RolModel.codigo == codigo.upper()))
        return m.rol_a_dominio(fila) if fila else None

    async def listar_todos(self) -> list[Rol]:
        filas = await self._s.scalars(self._base().order_by(RolModel.codigo))
        return [m.rol_a_dominio(f) for f in filas]

    async def agregar(self, rol: Rol) -> Rol:
        modelo = m.rol_a_modelo(rol)
        modelo.permisos = await self._modelos_de_permisos(rol)
        self._s.add(modelo)
        await self._s.flush()
        return rol

    async def actualizar(self, rol: Rol) -> Rol:
        modelo = await self._s.get(RolModel, rol.id, options=[selectinload(RolModel.permisos)])
        if modelo is None:
            raise ValueError(f"Rol inexistente: {rol.id}")
        m.rol_a_modelo(rol, modelo)
        modelo.permisos = await self._modelos_de_permisos(rol)
        await self._s.flush()
        return rol

    async def eliminar(self, rol_id: UUID) -> None:
        await self._s.execute(delete(RolModel).where(RolModel.id == rol_id))

    async def contar_usuarios(self, rol_id: UUID) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(usuario_roles)
                .where(usuario_roles.c.rol_id == rol_id)
            )
            or 0
        )

    async def _modelos_de_permisos(self, rol: Rol) -> list[PermisoModel]:
        if not rol.permisos:
            return []
        filas = await self._s.scalars(
            select(PermisoModel).where(PermisoModel.codigo.in_([p.value for p in rol.permisos]))
        )
        return list(filas)


class RepositorioTokensSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener_por_hash(self, hash_token: str) -> TokenRefresco | None:
        fila = await self._s.scalar(
            select(TokenRefrescoModel).where(TokenRefrescoModel.hash_token == hash_token)
        )
        return m.token_a_dominio(fila) if fila else None

    async def agregar(self, token: TokenRefresco) -> TokenRefresco:
        self._s.add(m.token_a_modelo(token))
        await self._s.flush()
        return token

    async def actualizar(self, token: TokenRefresco) -> TokenRefresco:
        modelo = await self._s.get(TokenRefrescoModel, token.id)
        if modelo is None:
            raise ValueError(f"Token inexistente: {token.id}")
        m.token_a_modelo(token, modelo)
        await self._s.flush()
        return token

    async def revocar_todos_de(self, usuario_id: UUID) -> int:
        resultado = cast(
            CursorResult[Any],
            await self._s.execute(
                update(TokenRefrescoModel)
                .where(
                    TokenRefrescoModel.usuario_id == usuario_id,
                    TokenRefrescoModel.revocado_en.is_(None),
                )
                .values(revocado_en=ahora_utc())
            ),
        )
        return resultado.rowcount or 0

    async def eliminar_expirados(self, antes_de: datetime) -> int:
        resultado = cast(
            CursorResult[Any],
            await self._s.execute(
                delete(TokenRefrescoModel).where(TokenRefrescoModel.expira_en < antes_de)
            ),
        )
        return resultado.rowcount or 0
