"""Proveedor de identidad contra LDAP / Active Directory.

`ldap3` es una dependencia opcional: si no esta instalada, el proveedor se
reporta como deshabilitado en lugar de romper el arranque. Una instalacion que
no usa directorio activo no deberia verse obligada a instalar la libreria.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import LDAPSettings
from app.core.logging import get_logger
from app.domain.enums import AuthProvider
from app.domain.errors import (
    CredencialesInvalidas,
    ErrorAutenticacion,
    ProveedorNoHabilitado,
)
from app.domain.ports.seguridad import IdentidadExterna

log = get_logger(__name__)

try:  # pragma: no cover - depende del entorno de instalacion
    from ldap3 import ALL, SIMPLE, Connection, Server
    from ldap3.core.exceptions import LDAPException

    LDAP_DISPONIBLE = True
except ImportError:  # pragma: no cover
    LDAP_DISPONIBLE = False
    LDAPException = Exception


class ProveedorLDAP:
    """Implementacion del puerto `ProveedorIdentidad` para directorio activo.

    Autentica en dos pasos, que es el patron correcto contra AD:

    1. Una cuenta de servicio busca al usuario y obtiene su DN.
    2. Se intenta un *bind* con ese DN y la contrasena que aporto la persona.

    Si el segundo paso tiene exito, la contrasena es correcta. El sistema nunca
    la almacena ni la compara: eso ocurre entero dentro del directorio.

    `ldap3` es sincrono, asi que cada operacion se ejecuta en un hilo aparte
    para no bloquear el bucle de eventos.
    """

    def __init__(self, config: LDAPSettings) -> None:
        self._cfg = config

    @property
    def tipo(self) -> AuthProvider:
        return AuthProvider.LDAP

    @property
    def esta_habilitado(self) -> bool:
        if self._cfg.enabled and not LDAP_DISPONIBLE:
            log.error(
                "LDAP_ENABLED=true pero la libreria ldap3 no esta instalada. "
                "Instale el extra: pip install '.[ldap]'"
            )
            return False
        return self._cfg.enabled

    async def autenticar(self, credencial: str, secreto: str | None = None) -> IdentidadExterna:
        if not self.esta_habilitado:
            raise ProveedorNoHabilitado("LDAP")
        if not secreto:
            raise CredencialesInvalidas("La contrasena es obligatoria para el acceso LDAP")

        usuario = credencial.strip()
        if not usuario or any(c in usuario for c in "()*\\\0"):
            # Caracteres con significado en un filtro LDAP: se rechazan en lugar
            # de escaparlos, porque un nombre de usuario no deberia contenerlos.
            raise CredencialesInvalidas("El nombre de usuario contiene caracteres no validos")

        return await asyncio.to_thread(self._autenticar_sincrono, usuario, secreto)

    # ------------------------------------------------------------ internos
    def _autenticar_sincrono(self, usuario: str, contrasena: str) -> IdentidadExterna:
        servidor = Server(
            self._cfg.server_uri,
            use_ssl=self._cfg.use_ssl,
            get_info=ALL,
            connect_timeout=self._cfg.timeout_seconds,
        )

        entrada = self._buscar_usuario(servidor, usuario)
        dn = entrada["dn"]

        try:
            conexion = Connection(
                servidor,
                user=dn,
                password=contrasena,
                authentication=SIMPLE,
                auto_bind=True,
                receive_timeout=self._cfg.timeout_seconds,
            )
            conexion.unbind()
        except LDAPException as exc:
            log.info("Credenciales LDAP rechazadas para %s", usuario)
            raise CredencialesInvalidas from exc

        atributos = entrada["attributes"]
        email = self._primer_valor(atributos.get(self._cfg.attr_email))
        if not email:
            raise ErrorAutenticacion(
                f"La cuenta '{usuario}' no tiene correo en el directorio; "
                "no es posible crear el perfil"
            )

        return IdentidadExterna(
            proveedor=AuthProvider.LDAP,
            identificador=dn,
            email=email.strip().lower(),
            nombre_completo=self._primer_valor(atributos.get(self._cfg.attr_full_name)) or usuario,
            email_verificado=True,
            atributos={"dn": dn, "usuario": usuario},
        )

    def _buscar_usuario(self, servidor: Any, usuario: str) -> dict[str, Any]:
        try:
            servicio = Connection(
                servidor,
                user=self._cfg.bind_dn or None,
                password=self._cfg.bind_password or None,
                authentication=SIMPLE if self._cfg.bind_dn else None,
                auto_bind=True,
                receive_timeout=self._cfg.timeout_seconds,
            )
        except LDAPException as exc:
            log.error("No fue posible conectar con el directorio: %s", exc)
            raise ErrorAutenticacion("El directorio no esta disponible") from exc

        try:
            servicio.search(
                search_base=self._cfg.user_search_base,
                search_filter=self._cfg.user_filter.format(username=usuario),
                attributes=[self._cfg.attr_email, self._cfg.attr_full_name],
                size_limit=2,
            )
            if not servicio.entries:
                # Se responde igual que ante una contrasena incorrecta: no se
                # revela que cuentas existen en el directorio.
                raise CredencialesInvalidas
            if len(servicio.entries) > 1:
                log.warning("El filtro LDAP devolvio varias entradas para %s", usuario)
                raise CredencialesInvalidas

            entrada = servicio.entries[0]
            return {
                "dn": str(entrada.entry_dn),
                "attributes": {
                    clave: valor.values if hasattr(valor, "values") else valor
                    for clave, valor in entrada.entry_attributes_as_dict.items()
                },
            }
        finally:
            servicio.unbind()

    @staticmethod
    def _primer_valor(valor: Any) -> str:
        if valor is None:
            return ""
        if isinstance(valor, list | tuple):
            return str(valor[0]) if valor else ""
        return str(valor)
