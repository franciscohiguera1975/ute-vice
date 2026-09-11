"""Entidades de identidad y control de acceso.

Las reglas de autorizacion viven aqui, no en los endpoints. `Usuario.puede()`
es la unica respuesta autorizada a "¿este usuario puede hacer esto?", y tanto la
API como la consola y —mas adelante— los agentes de IA preguntan por el mismo
sitio.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.domain.alcance import AlcanceAcademico
from app.domain.enums import AuthProvider, Permiso, RolCodigo
from app.domain.errors import ConflictoDeEstado, ReglaDeNegocioViolada
from app.domain.value_objects import Email, ahora_utc


# ---------------------------------------------------------------------------
@dataclass(eq=True, frozen=True, slots=True)
class PermisoEntidad:
    """Permiso persistido. Su identidad es el codigo, no el UUID."""

    codigo: Permiso
    nombre: str
    descripcion: str = ""
    modulo: str = "general"
    id: UUID | None = None

    def __hash__(self) -> int:
        return hash(self.codigo)


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Rol:
    """Agrupacion nombrada de permisos."""

    codigo: str
    nombre: str
    descripcion: str = ""
    permisos: set[Permiso] = field(default_factory=set)
    es_sistema: bool = False
    """Los roles de sistema se siembran al instalar y no pueden eliminarse."""
    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    @classmethod
    def desde_catalogo(cls, codigo: RolCodigo, permisos: frozenset[Permiso]) -> Rol:
        return cls(
            codigo=codigo.value,
            nombre=codigo.value.capitalize(),
            permisos=set(permisos),
            es_sistema=True,
        )

    def otorgar(self, permiso: Permiso) -> None:
        self.permisos.add(permiso)
        self.actualizado_en = ahora_utc()

    def revocar(self, permiso: Permiso) -> None:
        self.permisos.discard(permiso)
        self.actualizado_en = ahora_utc()

    def reemplazar_permisos(self, permisos: set[Permiso]) -> None:
        if self.es_sistema and self.codigo == RolCodigo.ADMIN.value:
            raise ReglaDeNegocioViolada(
                "Los permisos del rol ADMIN no pueden modificarse: "
                "dejaria el sistema sin forma de recuperar el control."
            )
        self.permisos = set(permisos)
        self.actualizado_en = ahora_utc()

    def asegurar_eliminable(self) -> None:
        if self.es_sistema:
            raise ReglaDeNegocioViolada(
                f"El rol '{self.codigo}' es del sistema y no puede eliminarse"
            )

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Rol) and otro.codigo == self.codigo

    def __hash__(self) -> int:
        return hash(self.codigo)


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Usuario:
    """Cuenta de acceso al sistema.

    El hash de contrasena es opcional a proposito: un usuario que entra por
    Google o por el directorio activo no tiene credencial local, y forzarlo a
    tener una seria crear un vector de ataque innecesario.
    """

    email: Email
    nombre_completo: str
    proveedor: AuthProvider = AuthProvider.LOCAL
    hash_contrasena: str | None = None
    identificador_externo: str | None = None
    """`sub` de Google o `objectGUID` de LDAP. Estable ante cambios de correo."""

    roles: set[Rol] = field(default_factory=set)
    activo: bool = True
    es_superusuario: bool = False
    """Puertas abiertas. Reservado a la cuenta de rescate inicial."""

    #: Facultades y carreras que esta cuenta puede consultar. Vacias no
    #: restringen nada: ver `domain/alcance.py`.
    facultades_ids: set[UUID] = field(default_factory=set)
    carreras_ids: set[UUID] = field(default_factory=set)

    intentos_fallidos: int = 0
    bloqueado_hasta: datetime | None = None
    ultimo_acceso: datetime | None = None
    debe_cambiar_contrasena: bool = False

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    # ---------------------------------------------------------------- acceso
    @property
    def permisos(self) -> frozenset[Permiso]:
        """Union de los permisos de todos sus roles."""
        if self.es_superusuario:
            return frozenset(Permiso)
        acumulado: set[Permiso] = set()
        for rol in self.roles:
            acumulado |= rol.permisos
        return frozenset(acumulado)

    def puede(self, permiso: Permiso) -> bool:
        """Unico predicado de autorizacion del sistema."""
        return self.es_superusuario or permiso in self.permisos

    def puede_todo(self, *permisos: Permiso) -> bool:
        return all(self.puede(p) for p in permisos)

    def puede_alguno(self, *permisos: Permiso) -> bool:
        return any(self.puede(p) for p in permisos)

    def tiene_rol(self, codigo: str | RolCodigo) -> bool:
        buscado = codigo.value if isinstance(codigo, RolCodigo) else codigo
        return any(r.codigo == buscado for r in self.roles)

    # --------------------------------------------------------------- alcance
    @property
    def alcance(self) -> AlcanceAcademico:
        """Que parte del distributivo ve esta cuenta.

        El superusuario no se acota nunca: es la cuenta de rescate, y dejarla
        sin ver algo podria impedir arreglar justamente eso.
        """
        if self.es_superusuario:
            return AlcanceAcademico.total()
        return AlcanceAcademico.de(self.facultades_ids, self.carreras_ids)

    def definir_alcance(
        self,
        facultades_ids: Iterable[UUID] | None = None,
        carreras_ids: Iterable[UUID] | None = None,
    ) -> None:
        """Reemplaza el alcance. Dos listas vacias lo dejan sin restriccion."""
        if facultades_ids is not None:
            self.facultades_ids = set(facultades_ids)
        if carreras_ids is not None:
            self.carreras_ids = set(carreras_ids)
        self.actualizado_en = ahora_utc()

    # ----------------------------------------------------------------- roles
    def asignar_rol(self, rol: Rol) -> None:
        self.roles.add(rol)
        self.actualizado_en = ahora_utc()

    def quitar_rol(self, rol: Rol) -> None:
        self.roles.discard(rol)
        self.actualizado_en = ahora_utc()

    def reemplazar_roles(self, roles: set[Rol]) -> None:
        if not roles and not self.es_superusuario:
            raise ReglaDeNegocioViolada("Un usuario debe conservar al menos un rol")
        self.roles = set(roles)
        self.actualizado_en = ahora_utc()

    # ------------------------------------------------------------ ciclo vida
    def activar(self) -> None:
        self.activo = True
        self.intentos_fallidos = 0
        self.bloqueado_hasta = None
        self.actualizado_en = ahora_utc()

    def desactivar(self) -> None:
        if self.es_superusuario:
            raise ReglaDeNegocioViolada(
                "El superusuario no puede desactivarse: dejaria el sistema sin acceso"
            )
        self.activo = False
        self.actualizado_en = ahora_utc()

    def asegurar_puede_iniciar_sesion(self, ahora: datetime | None = None) -> None:
        """Valida el estado de la cuenta. Lanza si no puede entrar.

        Se separa de la verificacion de contrasena para que el bloqueo por
        intentos aplique igual a Google y LDAP.
        """
        from app.domain.errors import UsuarioBloqueado, UsuarioInactivo

        if not self.activo:
            raise UsuarioInactivo
        ahora = ahora or ahora_utc()
        if self.bloqueado_hasta and self.bloqueado_hasta > ahora:
            restante = self.bloqueado_hasta - ahora
            raise UsuarioBloqueado(max(1, int(restante.total_seconds() // 60)))

    # -------------------------------------------------------- autenticacion
    def registrar_intento_fallido(
        self, *, maximo: int, minutos_bloqueo: int, ahora: datetime | None = None
    ) -> None:
        """Cuenta el fallo y bloquea al alcanzar el umbral."""
        ahora = ahora or ahora_utc()
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= maximo:
            self.bloqueado_hasta = ahora + timedelta(minutes=minutos_bloqueo)
        self.actualizado_en = ahora

    def registrar_acceso_exitoso(self, ahora: datetime | None = None) -> None:
        ahora = ahora or ahora_utc()
        self.intentos_fallidos = 0
        self.bloqueado_hasta = None
        self.ultimo_acceso = ahora
        self.actualizado_en = ahora

    def establecer_hash(self, hash_nuevo: str) -> None:
        if self.proveedor is not AuthProvider.LOCAL:
            raise ConflictoDeEstado(
                f"El usuario se autentica por {self.proveedor.value}; no admite contrasena local"
            )
        self.hash_contrasena = hash_nuevo
        self.debe_cambiar_contrasena = False
        self.actualizado_en = ahora_utc()

    @property
    def usa_credencial_local(self) -> bool:
        return self.proveedor is AuthProvider.LOCAL and self.hash_contrasena is not None

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Usuario) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class TokenRefresco:
    """Token de refresco persistido, para poder revocarlo.

    Se guarda el hash, nunca el token: si la base de datos se filtra, los tokens
    almacenados no sirven para suplantar a nadie.
    """

    usuario_id: UUID
    hash_token: str
    expira_en: datetime
    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    revocado_en: datetime | None = None
    reemplazado_por: UUID | None = None
    """Encadena la rotacion: permite detectar reutilizacion de un token viejo."""
    user_agent: str | None = None
    direccion_ip: str | None = None

    @property
    def esta_revocado(self) -> bool:
        return self.revocado_en is not None

    def esta_expirado(self, ahora: datetime | None = None) -> bool:
        return (ahora or ahora_utc()) >= self.expira_en

    def es_utilizable(self, ahora: datetime | None = None) -> bool:
        return not self.esta_revocado and not self.esta_expirado(ahora)

    def revocar(self, *, reemplazado_por: UUID | None = None) -> None:
        if self.esta_revocado:
            return
        self.revocado_en = ahora_utc()
        self.reemplazado_por = reemplazado_por
