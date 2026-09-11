"""Puertos de seguridad: hashing, tokens e identidades federadas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.enums import AuthProvider


class HasherContrasenas(Protocol):
    """Abstrae el algoritmo de derivacion de claves.

    Cambiar de Argon2 a lo que venga despues es reemplazar una implementacion,
    sin tocar un solo caso de uso.
    """

    def hashear(self, contrasena: str) -> str: ...

    def verificar(self, contrasena: str, hash_almacenado: str) -> bool:
        """Comprobacion en tiempo constante. Nunca lanza por hash malformado:
        devuelve `False`, para no filtrar informacion por el tipo de error."""
        ...

    def necesita_rehash(self, hash_almacenado: str) -> bool:
        """`True` si el hash usa parametros mas debiles que los actuales.

        Permite reforzar el coste de trabajo de forma transparente: al iniciar
        sesion con exito se rehashea con los parametros nuevos.
        """
        ...


@dataclass(frozen=True, slots=True)
class ContenidoToken:
    """Reclamaciones que viajan dentro de un token de acceso."""

    usuario_id: UUID
    email: str
    permisos: frozenset[str]
    tipo: str = "access"
    jti: str | None = None
    expira_en: datetime | None = None


@dataclass(frozen=True, slots=True)
class ParDeTokens:
    acceso: str
    refresco: str
    tipo: str = "bearer"
    expira_en_segundos: int = 0


class ServicioTokens(Protocol):
    """Emision y verificacion de tokens."""

    def emitir_acceso(self, contenido: ContenidoToken) -> tuple[str, datetime]:
        """Devuelve el token y su instante de expiracion."""
        ...

    def emitir_refresco(self, usuario_id: UUID) -> tuple[str, str, datetime]:
        """Devuelve `(token, hash_para_persistir, expiracion)`.

        El hash es lo unico que se guarda: el token en claro solo existe en la
        respuesta al cliente.
        """
        ...

    def decodificar_acceso(self, token: str) -> ContenidoToken:
        """Lanza `TokenInvalido` si la firma, el emisor o la vigencia fallan."""
        ...

    def hash_de_refresco(self, token: str) -> str:
        """Hash determinista, para buscar el token persistido."""
        ...


@dataclass(frozen=True, slots=True)
class IdentidadExterna:
    """Identidad devuelta por un proveedor federado, ya normalizada."""

    proveedor: AuthProvider
    identificador: str
    """Identificador estable del proveedor (`sub`, `objectGUID`)."""
    email: str
    nombre_completo: str
    email_verificado: bool = True
    atributos: dict[str, str] | None = None


class ProveedorIdentidad(Protocol):
    """Contrato comun a Google, LDAP y cualquier IdP futuro.

    Los casos de uso de inicio de sesion federado hablan con este puerto y no
    saben si detras hay OAuth o un directorio activo. Es sustitucion de Liskov
    aplicada al acceso: agregar un IdP no cambia el caso de uso.
    """

    @property
    def tipo(self) -> AuthProvider: ...

    @property
    def esta_habilitado(self) -> bool: ...

    async def autenticar(self, credencial: str, secreto: str | None = None) -> IdentidadExterna:
        """Valida la credencial y devuelve la identidad normalizada.

        `credencial` es el codigo de autorizacion en OAuth o el usuario en LDAP;
        `secreto` es la contrasena en LDAP y no se usa en OAuth.

        Lanza `ErrorAutenticacion` si la credencial no es valida y
        `ProveedorNoHabilitado` si el metodo esta apagado en la configuracion.
        """
        ...


class ProveedorOAuth(ProveedorIdentidad, Protocol):
    """Proveedor con flujo de redireccion (codigo de autorizacion)."""

    def url_autorizacion(self, estado: str) -> str:
        """URL a la que enviar al navegador para iniciar el flujo."""
        ...
