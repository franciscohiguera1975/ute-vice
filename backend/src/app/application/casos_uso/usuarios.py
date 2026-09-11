"""Casos de uso de administracion de usuarios y roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.auth import Rol, Usuario
from app.domain.enums import AuthProvider, Permiso
from app.domain.errors import (
    ErrorValidacion,
    NoEncontrado,
    ReglaDeNegocioViolada,
    YaExiste,
)
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.seguridad import HasherContrasenas
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import ContrasenaEnClaro, Email

# ---------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaCrearUsuario:
    email: str
    nombre_completo: str
    contrasena: str | None = None
    """`None` para cuentas federadas, que no tienen credencial local."""
    proveedor: AuthProvider = AuthProvider.LOCAL
    roles: tuple[str, ...] = ()
    activo: bool = True
    debe_cambiar_contrasena: bool = True


@dataclass(frozen=True, slots=True)
class EntradaActualizarUsuario:
    usuario_id: UUID
    nombre_completo: str | None = None
    email: str | None = None
    activo: bool | None = None
    roles: list[str] | None = None


@dataclass(frozen=True, slots=True)
class EntradaListarUsuarios:
    paginacion: Paginacion = field(default_factory=Paginacion)
    texto: str | None = None
    activo: bool | None = None
    rol: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaRestablecerContrasena:
    usuario_id: UUID
    contrasena_nueva: str
    forzar_cambio: bool = True


@dataclass(frozen=True, slots=True)
class EntradaActualizarRol:
    codigo: str
    nombre: str | None = None
    descripcion: str | None = None
    permisos: list[str] | None = None


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------


class CrearUsuario(CasoDeUso[EntradaCrearUsuario, Usuario]):
    """Da de alta una cuenta."""

    nombre = "usuarios.crear"
    descripcion = "Crea una cuenta de usuario y le asigna roles"
    permiso_requerido = Permiso.USUARIOS_ESCRIBIR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        hasher: HasherContrasenas,
        longitud_minima_contrasena: int = 10,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._min = longitud_minima_contrasena

    async def _ejecutar(self, entrada: EntradaCrearUsuario, contexto: ContextoEjecucion) -> Usuario:
        email = Email(entrada.email)

        async with self._uow:
            if await self._uow.usuarios.existe_email(email):
                raise YaExiste("usuario", "email", email.valor)

            hash_contrasena: str | None = None
            if entrada.proveedor is AuthProvider.LOCAL:
                if not entrada.contrasena:
                    raise ErrorValidacion(
                        "Una cuenta local requiere contrasena", campo="contrasena"
                    )
                clara = ContrasenaEnClaro(entrada.contrasena, longitud_minima=self._min)
                hash_contrasena = self._hasher.hashear(clara.valor)
            elif entrada.contrasena:
                raise ErrorValidacion(
                    f"Una cuenta {entrada.proveedor.value} no admite contrasena local",
                    campo="contrasena",
                )

            roles = await _resolver_roles(self._uow, list(entrada.roles))
            if not roles:
                raise ErrorValidacion("Debe asignarse al menos un rol", campo="roles")

            usuario = Usuario(
                email=email,
                nombre_completo=entrada.nombre_completo.strip(),
                proveedor=entrada.proveedor,
                hash_contrasena=hash_contrasena,
                roles=roles,
                activo=entrada.activo,
                debe_cambiar_contrasena=(
                    entrada.debe_cambiar_contrasena and entrada.proveedor is AuthProvider.LOCAL
                ),
            )
            creado = await self._uow.usuarios.agregar(usuario)
            await self._uow.commit()
            return creado


class ActualizarUsuario(CasoDeUso[EntradaActualizarUsuario, Usuario]):
    """Modifica datos y roles de una cuenta."""

    nombre = "usuarios.actualizar"
    descripcion = "Actualiza los datos o los roles de un usuario"
    permiso_requerido = Permiso.USUARIOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarUsuario, contexto: ContextoEjecucion
    ) -> Usuario:
        async with self._uow:
            usuario = await self._uow.usuarios.obtener(entrada.usuario_id)
            if usuario is None:
                raise NoEncontrado("Usuario", entrada.usuario_id)

            if entrada.email is not None:
                nuevo = Email(entrada.email)
                if await self._uow.usuarios.existe_email(nuevo, excluyendo=usuario.id):
                    raise YaExiste("usuario", "email", nuevo.valor)
                usuario.email = nuevo

            if entrada.nombre_completo is not None:
                usuario.nombre_completo = entrada.nombre_completo.strip()

            if entrada.activo is not None:
                await self._cambiar_estado(usuario, entrada.activo, contexto)

            if entrada.roles is not None:
                usuario.reemplazar_roles(await _resolver_roles(self._uow, entrada.roles))

            actualizado = await self._uow.usuarios.actualizar(usuario)
            await self._uow.commit()
            return actualizado

    async def _cambiar_estado(
        self, usuario: Usuario, activo: bool, contexto: ContextoEjecucion
    ) -> None:
        if activo:
            usuario.activar()
            return
        if contexto.actor and contexto.actor.id == usuario.id:
            raise ReglaDeNegocioViolada("No puede desactivar su propia cuenta")
        if usuario.es_superusuario and await self._uow.usuarios.contar_superusuarios_activos() <= 1:
            raise ReglaDeNegocioViolada(
                "Es el ultimo superusuario activo: desactivarlo dejaria el "
                "sistema sin administrador"
            )
        usuario.desactivar()
        # Una cuenta desactivada no debe conservar sesiones vivas.
        await self._uow.tokens.revocar_todos_de(usuario.id)


class ListarUsuarios(CasoDeUso[EntradaListarUsuarios, Pagina[Usuario]]):
    """Lista usuarios con filtros y paginacion."""

    nombre = "usuarios.listar"
    descripcion = "Lista las cuentas de usuario"
    permiso_requerido = Permiso.USUARIOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarUsuarios, contexto: ContextoEjecucion
    ) -> Pagina[Usuario]:
        async with self._uow:
            return await self._uow.usuarios.listar(
                entrada.paginacion,
                texto=entrada.texto,
                activo=entrada.activo,
                rol=entrada.rol,
            )


class ObtenerUsuario(CasoDeUso[UUID, Usuario]):
    nombre = "usuarios.obtener"
    descripcion = "Obtiene una cuenta de usuario por su identificador"
    permiso_requerido = Permiso.USUARIOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> Usuario:
        async with self._uow:
            usuario = await self._uow.usuarios.obtener(entrada)
            if usuario is None:
                raise NoEncontrado("Usuario", entrada)
            return usuario


class EliminarUsuario(CasoDeUso[UUID, None]):
    """Elimina una cuenta.

    Se prefiere desactivar antes que eliminar: los registros de auditoria
    referencian al usuario que ejecuto cada accion. Este caso de uso existe para
    depurar cuentas creadas por error, no como operacion rutinaria.
    """

    nombre = "usuarios.eliminar"
    descripcion = "Elimina definitivamente una cuenta de usuario"
    permiso_requerido = Permiso.USUARIOS_ELIMINAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            usuario = await self._uow.usuarios.obtener(entrada)
            if usuario is None:
                raise NoEncontrado("Usuario", entrada)
            if contexto.actor and contexto.actor.id == usuario.id:
                raise ReglaDeNegocioViolada("No puede eliminar su propia cuenta")
            if usuario.es_superusuario:
                raise ReglaDeNegocioViolada("El superusuario no puede eliminarse")

            await self._uow.tokens.revocar_todos_de(usuario.id)
            await self._uow.usuarios.eliminar(usuario.id)
            await self._uow.commit()


class RestablecerContrasena(CasoDeUso[EntradaRestablecerContrasena, None]):
    """Un administrador fija una contrasena nueva para otra cuenta."""

    nombre = "usuarios.restablecer_contrasena"
    descripcion = "Restablece la contrasena de un usuario"
    permiso_requerido = Permiso.USUARIOS_ESCRIBIR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        hasher: HasherContrasenas,
        longitud_minima_contrasena: int = 10,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._min = longitud_minima_contrasena

    async def _ejecutar(
        self, entrada: EntradaRestablecerContrasena, contexto: ContextoEjecucion
    ) -> None:
        async with self._uow:
            usuario = await self._uow.usuarios.obtener(entrada.usuario_id)
            if usuario is None:
                raise NoEncontrado("Usuario", entrada.usuario_id)

            clara = ContrasenaEnClaro(entrada.contrasena_nueva, longitud_minima=self._min)
            usuario.establecer_hash(self._hasher.hashear(clara.valor))
            usuario.debe_cambiar_contrasena = entrada.forzar_cambio
            usuario.activar()  # un restablecimiento tambien levanta el bloqueo

            await self._uow.usuarios.actualizar(usuario)
            await self._uow.tokens.revocar_todos_de(usuario.id)
            await self._uow.commit()


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


class ListarRoles(CasoDeUso[None, list[Rol]]):
    nombre = "roles.listar"
    descripcion = "Lista los roles definidos con sus permisos"
    permiso_requerido = Permiso.USUARIOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[Rol]:
        async with self._uow:
            return await self._uow.roles.listar_todos()


class ActualizarRol(CasoDeUso[EntradaActualizarRol, Rol]):
    """Modifica el conjunto de permisos de un rol."""

    nombre = "roles.actualizar"
    descripcion = "Cambia el nombre, la descripcion o los permisos de un rol"
    permiso_requerido = Permiso.ROLES_ADMINISTRAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaActualizarRol, contexto: ContextoEjecucion) -> Rol:
        async with self._uow:
            rol = await self._uow.roles.obtener_por_codigo(entrada.codigo)
            if rol is None:
                raise NoEncontrado("Rol", entrada.codigo)

            if entrada.nombre is not None:
                rol.nombre = entrada.nombre.strip()
            if entrada.descripcion is not None:
                rol.descripcion = entrada.descripcion.strip()
            if entrada.permisos is not None:
                rol.reemplazar_permisos(_parsear_permisos(entrada.permisos))

            actualizado = await self._uow.roles.actualizar(rol)
            await self._uow.commit()
            return actualizado


class ListarPermisos(CasoDeUso[None, list[dict[str, str]]]):
    """Catalogo completo de permisos, agrupado por modulo.

    El frontend lo usa para pintar la matriz de roles sin tener que mantener su
    propia copia de la lista — que inevitablemente se desincronizaria.
    """

    nombre = "roles.listar_permisos"
    descripcion = "Catalogo de permisos disponibles en el sistema"
    permiso_requerido = Permiso.USUARIOS_LEER

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[dict[str, str]]:
        return [
            {
                "codigo": p.value,
                "modulo": p.value.split(":")[0],
                "accion": p.value.split(":")[1],
            }
            for p in Permiso
        ]


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


async def _resolver_roles(uow: UnidadDeTrabajo, codigos: list[str]) -> set[Rol]:
    """Convierte codigos en entidades, fallando ante cualquiera desconocido."""
    roles: set[Rol] = set()
    for codigo in codigos:
        rol = await uow.roles.obtener_por_codigo(codigo.strip().upper())
        if rol is None:
            raise NoEncontrado("Rol", codigo)
        roles.add(rol)
    return roles


def _parsear_permisos(codigos: list[str]) -> set[Permiso]:
    permisos: set[Permiso] = set()
    for codigo in codigos:
        try:
            permisos.add(Permiso(codigo.strip()))
        except ValueError:
            raise ErrorValidacion(f"Permiso desconocido: {codigo}", campo="permisos") from None
    return permisos
