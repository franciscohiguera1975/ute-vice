"""Dependencias de FastAPI: inyeccion, autenticacion y autorizacion."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.base import ContextoEjecucion
from app.core.config import Settings
from app.core.logging import user_id_ctx
from app.domain.entities.auth import Usuario
from app.domain.enums import Permiso
from app.domain.errors import ErrorAutorizacion, TokenInvalido, UsuarioInactivo
from app.domain.ports.uow import UnidadDeTrabajo
from app.infrastructure.contenedor import Contenedor

#: `auto_error=False` para que la ausencia de cabecera llegue como `None` y sea
#: nuestro codigo —y no Starlette— quien produzca el error con nuestro formato.
esquema_bearer = HTTPBearer(auto_error=False, description="Token de acceso JWT")


# ---------------------------------------------------------------------------
# Infraestructura
# ---------------------------------------------------------------------------


def obtener_contenedor(request: Request) -> Contenedor:
    """Contenedor construido al arrancar y guardado en el estado de la app."""
    contenedor: Contenedor = request.app.state.contenedor
    return contenedor


ContenedorDep = Annotated[Contenedor, Depends(obtener_contenedor)]


def obtener_settings(contenedor: ContenedorDep) -> Settings:
    return contenedor.settings


SettingsDep = Annotated[Settings, Depends(obtener_settings)]


async def obtener_uow(contenedor: ContenedorDep) -> AsyncIterator[UnidadDeTrabajo]:
    """Una unidad de trabajo por peticion.

    No se abre la transaccion aqui: cada caso de uso declara su propio limite
    con `async with uow`. Asi una peticion que ejecuta dos casos de uso obtiene
    dos transacciones independientes, que es lo correcto.
    """
    uow = contenedor.unidad_de_trabajo()
    yield uow


UowDep = Annotated[UnidadDeTrabajo, Depends(obtener_uow)]


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------


async def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    contenedor: ContenedorDep,
    uow: UowDep,
) -> Usuario:
    """Resuelve el usuario a partir del token de acceso.

    El token trae los permisos, pero el usuario se recarga de la base en cada
    peticion. Es un viaje mas, y es intencional: sin el, revocar un rol no
    tendria efecto hasta que expirara el token, y una cuenta desactivada seguiria
    operando durante media hora.
    """
    if credenciales is None or not credenciales.credentials:
        raise TokenInvalido("Falta el token de acceso")

    contenido = contenedor.tokens.decodificar_acceso(credenciales.credentials)

    async with uow:
        usuario = await uow.usuarios.obtener(contenido.usuario_id)

    if usuario is None:
        raise TokenInvalido("El usuario del token ya no existe")
    if not usuario.activo:
        raise UsuarioInactivo

    user_id_ctx.set(str(usuario.id))
    return usuario


UsuarioDep = Annotated[Usuario, Depends(usuario_actual)]


async def usuario_opcional(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    contenedor: ContenedorDep,
    uow: UowDep,
) -> Usuario | None:
    """Igual que `usuario_actual`, pero devuelve `None` si no hay sesion."""
    if credenciales is None or not credenciales.credentials:
        return None
    try:
        return await usuario_actual(credenciales, contenedor, uow)
    except (TokenInvalido, UsuarioInactivo):
        return None


UsuarioOpcionalDep = Annotated[Usuario | None, Depends(usuario_opcional)]


# ---------------------------------------------------------------------------
# Contexto de ejecucion
# ---------------------------------------------------------------------------


def _contexto(request: Request, actor: Usuario | None) -> ContextoEjecucion:
    return ContextoEjecucion(
        actor=actor,
        direccion_ip=_ip_cliente(request),
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )


async def contexto_autenticado(request: Request, actor: UsuarioDep) -> ContextoEjecucion:
    return _contexto(request, actor)


async def contexto_anonimo(request: Request, actor: UsuarioOpcionalDep) -> ContextoEjecucion:
    return _contexto(request, actor)


ContextoDep = Annotated[ContextoEjecucion, Depends(contexto_autenticado)]
ContextoAnonimoDep = Annotated[ContextoEjecucion, Depends(contexto_anonimo)]


def _ip_cliente(request: Request) -> str | None:
    """IP del cliente, considerando el proxy inverso.

    Se toma la primera entrada de `X-Forwarded-For`, que es la del cliente
    original. Solo es fiable si el proxy que tenemos delante la reescribe; si la
    aplicacion se expusiera directamente, un cliente podria falsear la cabecera.
    """
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Autorizacion
# ---------------------------------------------------------------------------


def requiere(*permisos: Permiso):  # type: ignore[no-untyped-def]
    """Dependencia que exige uno o mas permisos.

    Es una segunda linea de defensa: el caso de uso ya verifica su propio
    permiso. Ponerla tambien en el endpoint hace que la exigencia sea visible en
    la documentacion de OpenAPI y evita ejecutar trabajo que va a ser rechazado.

    Se exigen **todos** los permisos indicados.
    """

    async def verificar(usuario: UsuarioDep) -> Usuario:
        faltantes = [p for p in permisos if not usuario.puede(p)]
        if faltantes:
            raise ErrorAutorizacion(faltantes[0].value)
        return usuario

    return Depends(verificar)


def requiere_alguno(*permisos: Permiso):  # type: ignore[no-untyped-def]
    """Igual que `requiere`, pero basta con tener uno de los permisos."""

    async def verificar(usuario: UsuarioDep) -> Usuario:
        if not usuario.puede_alguno(*permisos):
            raise ErrorAutorizacion(" o ".join(p.value for p in permisos))
        return usuario

    return Depends(verificar)
