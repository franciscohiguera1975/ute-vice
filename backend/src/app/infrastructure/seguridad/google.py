"""Proveedor de identidad Google OAuth 2.0 / OpenID Connect."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import GoogleOAuthSettings
from app.core.logging import get_logger
from app.domain.enums import AuthProvider
from app.domain.errors import (
    CredencialesInvalidas,
    ErrorAutenticacion,
    ProveedorNoHabilitado,
)
from app.domain.ports.seguridad import IdentidadExterna

log = get_logger(__name__)


class ProveedorGoogle:
    """Implementacion del puerto `ProveedorOAuth` para Google.

    Flujo de codigo de autorizacion: el navegador vuelve con un codigo de un
    solo uso, el backend lo canjea por un token y con el consulta el perfil. El
    `client_secret` nunca sale del servidor — por eso el canje no se hace en el
    frontend.
    """

    def __init__(
        self, config: GoogleOAuthSettings, cliente: httpx.AsyncClient | None = None
    ) -> None:
        self._cfg = config
        self._cliente = cliente
        self._propio = cliente is None

    @property
    def tipo(self) -> AuthProvider:
        return AuthProvider.GOOGLE

    @property
    def esta_habilitado(self) -> bool:
        return self._cfg.enabled

    def url_autorizacion(self, estado: str) -> str:
        """URL a la que redirigir el navegador para iniciar el flujo.

        `state` es obligatorio: sin el, un tercero podria inducir al usuario a
        completar un inicio de sesion que no pidio (CSRF sobre el callback).
        """
        if not self.esta_habilitado:
            raise ProveedorNoHabilitado("GOOGLE")

        parametros = {
            "client_id": self._cfg.client_id,
            "redirect_uri": self._cfg.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": estado,
            "access_type": "offline",
            "prompt": "select_account",
        }
        if self._cfg.allowed_domains:
            # Sugerencia al selector de cuentas; no sustituye la validacion.
            parametros["hd"] = self._cfg.allowed_domains[0]

        return f"{self._cfg.authorize_url}?{httpx.QueryParams(parametros)}"

    async def autenticar(self, credencial: str, secreto: str | None = None) -> IdentidadExterna:
        """Canjea el codigo de autorizacion y devuelve la identidad."""
        if not self.esta_habilitado:
            raise ProveedorNoHabilitado("GOOGLE")

        cliente = self._cliente or httpx.AsyncClient(timeout=15.0)
        try:
            token_acceso = await self._canjear_codigo(cliente, credencial)
            perfil = await self._obtener_perfil(cliente, token_acceso)
        finally:
            if self._propio:
                await cliente.aclose()

        email = str(perfil.get("email") or "").strip().lower()
        if not email:
            raise ErrorAutenticacion("Google no devolvio un correo asociado a la cuenta")

        if not perfil.get("email_verified", False):
            raise ErrorAutenticacion("El correo de la cuenta de Google no esta verificado")

        if not self._cfg.dominio_permitido(email):
            raise CredencialesInvalidas(
                f"El dominio del correo no esta autorizado. "
                f"Dominios permitidos: {', '.join(self._cfg.allowed_domains)}"
            )

        return IdentidadExterna(
            proveedor=AuthProvider.GOOGLE,
            identificador=str(perfil["sub"]),
            email=email,
            nombre_completo=str(perfil.get("name") or email.split("@")[0]),
            email_verificado=True,
            atributos={
                "picture": str(perfil.get("picture", "")),
                "locale": str(perfil.get("locale", "")),
            },
        )

    # ------------------------------------------------------------ internos
    async def _canjear_codigo(self, cliente: httpx.AsyncClient, codigo: str) -> str:
        try:
            respuesta = await cliente.post(
                self._cfg.token_url,
                data={
                    "code": codigo,
                    "client_id": self._cfg.client_id,
                    "client_secret": self._cfg.client_secret,
                    "redirect_uri": self._cfg.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            log.warning("Fallo de red al canjear el codigo con Google: %s", exc)
            raise ErrorAutenticacion("No fue posible contactar a Google") from exc

        if respuesta.status_code != 200:
            log.warning(
                "Google rechazo el canje del codigo",
                extra={"estado": respuesta.status_code},
            )
            raise CredencialesInvalidas("El codigo de autorizacion no es valido o ya se uso")

        datos = respuesta.json()
        if "access_token" not in datos:
            raise ErrorAutenticacion("Google no devolvio un token de acceso")
        return str(datos["access_token"])

    async def _obtener_perfil(
        self, cliente: httpx.AsyncClient, token_acceso: str
    ) -> dict[str, Any]:
        try:
            respuesta = await cliente.get(
                self._cfg.userinfo_url,
                headers={"Authorization": f"Bearer {token_acceso}"},
            )
        except httpx.HTTPError as exc:
            raise ErrorAutenticacion("No fue posible obtener el perfil de Google") from exc

        if respuesta.status_code != 200:
            raise ErrorAutenticacion("Google rechazo la consulta del perfil")

        perfil: dict[str, Any] = respuesta.json()
        if "sub" not in perfil:
            raise ErrorAutenticacion("La respuesta de Google no incluye identificador")
        return perfil
