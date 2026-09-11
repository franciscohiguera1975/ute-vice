"""Emision y verificacion de tokens JWT."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import JWTSettings
from app.domain.errors import TokenInvalido
from app.domain.ports.seguridad import ContenidoToken


class ServicioTokensJWT:
    """Implementacion del puerto `ServicioTokens`.

    El token de acceso es un JWT firmado que transporta los permisos, de modo
    que autorizar una peticion no exige ir a la base de datos. El de refresco,
    en cambio, es un secreto opaco: se guarda su hash y se puede revocar. Los
    JWT no se revocan, y para una sesion larga esa capacidad es indispensable.
    """

    def __init__(self, config: JWTSettings) -> None:
        self._cfg = config

    # ------------------------------------------------------------- acceso
    def emitir_acceso(self, contenido: ContenidoToken) -> tuple[str, datetime]:
        ahora = datetime.now(UTC)
        expira = ahora + timedelta(minutes=self._cfg.access_token_expire_minutes)

        cuerpo = {
            "sub": str(contenido.usuario_id),
            "email": contenido.email,
            "permisos": sorted(contenido.permisos),
            "tipo": "access",
            "iat": int(ahora.timestamp()),
            "exp": int(expira.timestamp()),
            "iss": self._cfg.issuer,
            "aud": self._cfg.audience,
            "jti": secrets.token_urlsafe(16),
        }
        token = jwt.encode(cuerpo, self._cfg.secret_key, algorithm=self._cfg.algorithm)
        return token, expira

    def decodificar_acceso(self, token: str) -> ContenidoToken:
        try:
            cuerpo = jwt.decode(
                token,
                self._cfg.secret_key,
                algorithms=[self._cfg.algorithm],
                issuer=self._cfg.issuer,
                audience=self._cfg.audience,
                options={"require": ["exp", "iat", "sub"]},
            )
        except InvalidTokenError as exc:
            raise TokenInvalido(str(exc)) from exc

        if cuerpo.get("tipo") != "access":
            # Un token de refresco no debe servir para autorizar peticiones.
            raise TokenInvalido("El token no es de acceso")

        try:
            usuario_id = UUID(cuerpo["sub"])
        except (KeyError, ValueError) as exc:
            raise TokenInvalido("El token no identifica a un usuario valido") from exc

        return ContenidoToken(
            usuario_id=usuario_id,
            email=cuerpo.get("email", ""),
            permisos=frozenset(cuerpo.get("permisos", [])),
            tipo="access",
            jti=cuerpo.get("jti"),
            expira_en=datetime.fromtimestamp(cuerpo["exp"], tz=UTC),
        )

    # ------------------------------------------------------------ refresco
    def emitir_refresco(self, usuario_id: UUID) -> tuple[str, str, datetime]:
        """Genera un secreto opaco y devuelve `(token, hash, expiracion)`."""
        token = secrets.token_urlsafe(48)
        expira = datetime.now(UTC) + timedelta(days=self._cfg.refresh_token_expire_days)
        return token, self.hash_de_refresco(token), expira

    def hash_de_refresco(self, token: str) -> str:
        """HMAC-SHA256 con la clave del servicio.

        Se usa HMAC y no un hash simple para que quien obtenga la base de datos
        no pueda construir la tabla de correspondencias sin conocer tambien la
        clave de la aplicacion.
        """
        return hmac.new(self._cfg.secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()
