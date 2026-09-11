"""Endpoints de autenticacion."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import RedirectResponse

from app.api.dependencias import (
    ContenedorDep,
    ContextoAnonimoDep,
    ContextoDep,
    UowDep,
    UsuarioDep,
)
from app.api.esquemas.auth import (
    MetodosAccesoSalida,
    PerfilSalida,
    PeticionCambioContrasena,
    PeticionInicioLDAP,
    PeticionInicioSesion,
    PeticionRefresco,
    SesionSalida,
)
from app.api.esquemas.comunes import RespuestaMensaje
from app.application.casos_uso.autenticacion import (
    CambiarContrasenaPropia,
    CerrarSesion,
    CerrarTodasLasSesiones,
    EntradaCambioContrasena,
    EntradaInicioFederado,
    EntradaInicioSesion,
    EntradaRefresco,
    IniciarSesion,
    IniciarSesionFederado,
    ObtenerPerfil,
    RefrescarSesion,
)
from app.domain.enums import AuthProvider

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


@router.get(
    "/metodos",
    response_model=MetodosAccesoSalida,
    summary="Metodos de acceso habilitados",
)
async def metodos_acceso(contenedor: ContenedorDep) -> MetodosAccesoSalida:
    """Indica que vias de acceso estan activas en esta instalacion.

    Es publico y sin autenticar: la pantalla de acceso lo consulta antes de
    pintarse para no ofrecer un boton que no funciona.
    """
    cfg = contenedor.settings
    url_google = None
    if cfg.google.enabled:
        url_google = contenedor.proveedor_google.url_autorizacion(secrets.token_urlsafe(24))
    return MetodosAccesoSalida(
        local=True,
        google=cfg.google.enabled,
        ldap=cfg.ldap.enabled,
        url_google=url_google,
    )


@router.post(
    "/login",
    response_model=SesionSalida,
    summary="Iniciar sesion con credenciales locales",
    responses={
        401: {"description": "Credenciales invalidas"},
        403: {"description": "Cuenta desactivada"},
        429: {"description": "Cuenta bloqueada por intentos fallidos"},
    },
)
async def login(
    peticion: PeticionInicioSesion,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoAnonimoDep,
) -> SesionSalida:
    caso = IniciarSesion(
        uow,
        contenedor.hasher,
        contenedor.tokens,
        contenedor.reloj,
        contenedor.politica_acceso,
    )
    sesion = await caso(
        EntradaInicioSesion(email=peticion.email, contrasena=peticion.contrasena),
        contexto,
    )
    return SesionSalida.desde(sesion)


@router.post(
    "/login/ldap",
    response_model=SesionSalida,
    summary="Iniciar sesion contra el directorio activo",
    responses={501: {"description": "El acceso LDAP no esta habilitado"}},
)
async def login_ldap(
    peticion: PeticionInicioLDAP,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoAnonimoDep,
) -> SesionSalida:
    caso = IniciarSesionFederado(
        uow,
        contenedor.proveedores_identidad,
        contenedor.tokens,
        contenedor.reloj,
        contenedor.politica_acceso,
    )
    sesion = await caso(
        EntradaInicioFederado(
            proveedor=AuthProvider.LDAP,
            credencial=peticion.usuario,
            secreto=peticion.contrasena,
        ),
        contexto,
    )
    return SesionSalida.desde(sesion)


@router.get(
    "/google/autorizar",
    summary="Iniciar el flujo de acceso con Google",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses={501: {"description": "El acceso con Google no esta habilitado"}},
)
async def google_autorizar(contenedor: ContenedorDep) -> RedirectResponse:
    """Redirige al selector de cuentas de Google."""
    url = contenedor.proveedor_google.url_autorizacion(secrets.token_urlsafe(24))
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get(
    "/google/callback",
    response_model=SesionSalida,
    summary="Retorno del flujo de Google",
)
async def google_callback(
    code: Annotated[str, Query(description="Codigo de autorizacion devuelto por Google")],
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoAnonimoDep,
) -> SesionSalida:
    """Canjea el codigo de autorizacion y abre la sesion.

    El canje ocurre en el servidor porque exige el `client_secret`, que nunca
    debe llegar al navegador.
    """
    caso = IniciarSesionFederado(
        uow,
        contenedor.proveedores_identidad,
        contenedor.tokens,
        contenedor.reloj,
        contenedor.politica_acceso,
    )
    sesion = await caso(
        EntradaInicioFederado(proveedor=AuthProvider.GOOGLE, credencial=code),
        contexto,
    )
    return SesionSalida.desde(sesion)


@router.post(
    "/refrescar",
    response_model=SesionSalida,
    summary="Renovar el par de tokens",
    responses={401: {"description": "Token de refresco invalido, expirado o reutilizado"}},
)
async def refrescar(
    peticion: PeticionRefresco,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoAnonimoDep,
) -> SesionSalida:
    caso = RefrescarSesion(uow, contenedor.tokens, contenedor.reloj, contenedor.politica_acceso)
    sesion = await caso(EntradaRefresco(token_refresco=peticion.token_refresco), contexto)
    return SesionSalida.desde(sesion)


@router.post(
    "/logout",
    response_model=RespuestaMensaje,
    summary="Cerrar la sesion actual",
)
async def logout(
    peticion: PeticionRefresco,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoAnonimoDep,
) -> RespuestaMensaje:
    caso = CerrarSesion(uow, contenedor.tokens)
    await caso(EntradaRefresco(token_refresco=peticion.token_refresco), contexto)
    return RespuestaMensaje(mensaje="Sesion cerrada correctamente")


@router.post(
    "/logout-todas",
    response_model=RespuestaMensaje,
    summary="Cerrar todas las sesiones propias",
)
async def logout_todas(uow: UowDep, usuario: UsuarioDep, contexto: ContextoDep) -> RespuestaMensaje:
    caso = CerrarTodasLasSesiones(uow)
    cerradas = await caso(usuario.id, contexto)
    return RespuestaMensaje(mensaje=f"Se cerraron {cerradas} sesion(es)")


@router.get(
    "/perfil",
    response_model=PerfilSalida,
    summary="Perfil y permisos del usuario autenticado",
)
async def perfil(uow: UowDep, contexto: ContextoDep) -> PerfilSalida:
    caso = ObtenerPerfil(uow)
    return PerfilSalida.desde(await caso(None, contexto))


@router.post(
    "/cambiar-contrasena",
    response_model=RespuestaMensaje,
    summary="Cambiar la contrasena propia",
    responses={401: {"description": "La contrasena actual no es correcta"}},
)
async def cambiar_contrasena(
    peticion: PeticionCambioContrasena,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
) -> RespuestaMensaje:
    caso = CambiarContrasenaPropia(uow, contenedor.hasher, contenedor.politica_acceso)
    await caso(
        EntradaCambioContrasena(
            contrasena_actual=peticion.contrasena_actual,
            contrasena_nueva=peticion.contrasena_nueva,
        ),
        contexto,
    )
    return RespuestaMensaje(
        mensaje="Contrasena actualizada. Las demas sesiones se cerraron por seguridad."
    )
