"""Endpoints de administracion de usuarios, roles y permisos."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import ContenedorDep, ContextoDep, UowDep, requiere
from app.api.esquemas.auth import UsuarioSalida
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.nucleo import (
    PermisoSalida,
    RestablecerContrasenaEntrada,
    RolActualizar,
    RolSalida,
    UsuarioActualizar,
    UsuarioCrear,
)
from app.application.casos_uso.usuarios import (
    ActualizarRol,
    ActualizarUsuario,
    CrearUsuario,
    EliminarUsuario,
    EntradaActualizarRol,
    EntradaActualizarUsuario,
    EntradaCrearUsuario,
    EntradaListarUsuarios,
    EntradaRestablecerContrasena,
    ListarPermisos,
    ListarRoles,
    ListarUsuarios,
    ObtenerUsuario,
    RestablecerContrasena,
)
from app.domain.enums import Permiso

router = APIRouter(tags=["Administracion"])


# ===========================================================================
# Usuarios
# ===========================================================================


@router.get(
    "/usuarios",
    response_model=RespuestaPaginada[UsuarioSalida],
    summary="Listar usuarios",
    dependencies=[requiere(Permiso.USUARIOS_LEER)],
)
async def listar_usuarios(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[str | None, Query(description="Busqueda por nombre o correo")] = None,
    activo: bool | None = None,
    rol: Annotated[str | None, Query(description="Codigo de rol, p. ej. ANALISTA")] = None,
) -> RespuestaPaginada[UsuarioSalida]:
    caso = ListarUsuarios(uow)
    pagina = await caso(
        EntradaListarUsuarios(
            paginacion=paginacion.a_dominio(), texto=texto, activo=activo, rol=rol
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [UsuarioSalida.desde(u) for u in pagina.items])


@router.post(
    "/usuarios",
    response_model=UsuarioSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario",
    dependencies=[requiere(Permiso.USUARIOS_ESCRIBIR)],
    responses={409: {"description": "Ya existe un usuario con ese correo"}},
)
async def crear_usuario(
    datos: UsuarioCrear, contenedor: ContenedorDep, uow: UowDep, contexto: ContextoDep
) -> UsuarioSalida:
    caso = CrearUsuario(uow, contenedor.hasher, contenedor.settings.security.password_min_length)
    usuario = await caso(
        EntradaCrearUsuario(
            email=datos.email,
            nombre_completo=datos.nombre_completo,
            contrasena=datos.contrasena,
            roles=tuple(datos.roles),
            activo=datos.activo,
            debe_cambiar_contrasena=datos.debe_cambiar_contrasena,
        ),
        contexto,
    )
    return UsuarioSalida.desde(usuario)


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioSalida,
    summary="Obtener un usuario",
    dependencies=[requiere(Permiso.USUARIOS_LEER)],
)
async def obtener_usuario(usuario_id: UUID, uow: UowDep, contexto: ContextoDep) -> UsuarioSalida:
    caso = ObtenerUsuario(uow)
    return UsuarioSalida.desde(await caso(usuario_id, contexto))


@router.patch(
    "/usuarios/{usuario_id}",
    response_model=UsuarioSalida,
    summary="Actualizar un usuario o sus roles",
    dependencies=[requiere(Permiso.USUARIOS_ESCRIBIR)],
    responses={
        422: {
            "description": (
                "Reglas de proteccion: no puede desactivar su propia cuenta ni "
                "dejar el sistema sin superusuario activo"
            )
        }
    },
)
async def actualizar_usuario(
    usuario_id: UUID, datos: UsuarioActualizar, uow: UowDep, contexto: ContextoDep
) -> UsuarioSalida:
    """Al desactivar una cuenta se revocan todas sus sesiones abiertas."""
    caso = ActualizarUsuario(uow)
    usuario = await caso(
        EntradaActualizarUsuario(
            usuario_id=usuario_id,
            nombre_completo=datos.nombre_completo,
            email=datos.email,
            activo=datos.activo,
            roles=datos.roles,
        ),
        contexto,
    )
    return UsuarioSalida.desde(usuario)


@router.post(
    "/usuarios/{usuario_id}/contrasena",
    response_model=RespuestaMensaje,
    summary="Restablecer la contrasena de un usuario",
    dependencies=[requiere(Permiso.USUARIOS_ESCRIBIR)],
)
async def restablecer_contrasena(
    usuario_id: UUID,
    datos: RestablecerContrasenaEntrada,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
) -> RespuestaMensaje:
    """Fija una contrasena nueva, levanta el bloqueo y cierra sus sesiones."""
    caso = RestablecerContrasena(
        uow, contenedor.hasher, contenedor.settings.security.password_min_length
    )
    await caso(
        EntradaRestablecerContrasena(
            usuario_id=usuario_id,
            contrasena_nueva=datos.contrasena_nueva,
            forzar_cambio=datos.forzar_cambio,
        ),
        contexto,
    )
    return RespuestaMensaje(
        mensaje="Contrasena restablecida. Las sesiones del usuario se cerraron."
    )


@router.delete(
    "/usuarios/{usuario_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar un usuario",
    dependencies=[requiere(Permiso.USUARIOS_ELIMINAR)],
)
async def eliminar_usuario(
    usuario_id: UUID, uow: UowDep, contexto: ContextoDep
) -> RespuestaMensaje:
    """Preferir la desactivacion: los registros de auditoria referencian al
    usuario que ejecuto cada accion."""
    caso = EliminarUsuario(uow)
    await caso(usuario_id, contexto)
    return RespuestaMensaje(mensaje="Usuario eliminado")


# ===========================================================================
# Roles y permisos
# ===========================================================================


@router.get(
    "/roles",
    response_model=list[RolSalida],
    summary="Listar roles con sus permisos",
    dependencies=[requiere(Permiso.USUARIOS_LEER)],
)
async def listar_roles(uow: UowDep, contexto: ContextoDep) -> list[RolSalida]:
    caso = ListarRoles(uow)
    return [RolSalida.desde(r) for r in await caso(None, contexto)]


@router.patch(
    "/roles/{codigo}",
    response_model=RolSalida,
    summary="Modificar un rol",
    dependencies=[requiere(Permiso.ROLES_ADMINISTRAR)],
    responses={422: {"description": "Los permisos del rol ADMIN no pueden modificarse"}},
)
async def actualizar_rol(
    codigo: str, datos: RolActualizar, uow: UowDep, contexto: ContextoDep
) -> RolSalida:
    caso = ActualizarRol(uow)
    rol = await caso(
        EntradaActualizarRol(
            codigo=codigo,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
            permisos=datos.permisos,
        ),
        contexto,
    )
    return RolSalida.desde(rol)


@router.get(
    "/permisos",
    response_model=list[PermisoSalida],
    summary="Catalogo de permisos del sistema",
    dependencies=[requiere(Permiso.USUARIOS_LEER)],
)
async def listar_permisos(contexto: ContextoDep) -> list[PermisoSalida]:
    """El frontend pinta la matriz de roles con esta lista.

    Se sirve desde el backend para que no exista una copia duplicada —y
    fatalmente desincronizada— en el codigo del cliente.
    """
    caso = ListarPermisos()
    return [PermisoSalida(**p) for p in await caso(None, contexto)]
