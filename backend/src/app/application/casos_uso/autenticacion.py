"""Casos de uso de autenticacion.

Tres vias de acceso conviven: credencial local, Google OAuth y directorio
activo. Las tres terminan en el mismo sitio —`_emitir_sesion`— porque las reglas
posteriores (cuenta activa, bloqueo por intentos, emision y rotacion de tokens)
son identicas. Lo unico que cambia es como se prueba la identidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.auth import TokenRefresco, Usuario
from app.domain.enums import AuthProvider, Permiso, RolCodigo
from app.domain.errors import (
    ConflictoDeEstado,
    CredencialesInvalidas,
    ErrorValidacion,
    NoEncontrado,
    ProveedorNoHabilitado,
    TokenInvalido,
    UsuarioInactivo,
)
from app.domain.ports.reloj import Reloj
from app.domain.ports.seguridad import (
    ContenidoToken,
    HasherContrasenas,
    IdentidadExterna,
    ParDeTokens,
    ProveedorIdentidad,
    ServicioTokens,
)
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import ContrasenaEnClaro, Email

# ---------------------------------------------------------------------------
# Configuracion que los casos de uso necesitan del entorno
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoliticaAcceso:
    max_intentos_fallidos: int = 5
    minutos_bloqueo: int = 15
    dias_refresco: int = 7
    longitud_minima_contrasena: int = 10
    rol_por_defecto_federado: str = RolCodigo.CONSULTA.value


# ---------------------------------------------------------------------------
# Entradas y salidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaInicioSesion:
    email: str
    contrasena: str


@dataclass(frozen=True, slots=True)
class EntradaInicioFederado:
    """Credencial de un proveedor externo.

    En Google, `credencial` es el codigo de autorizacion devuelto por el
    navegador. En LDAP, es el nombre de usuario y `secreto` la contrasena, que
    se valida contra el directorio y nunca se almacena aqui.
    """

    proveedor: AuthProvider
    credencial: str
    secreto: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaRefresco:
    token_refresco: str


@dataclass(frozen=True, slots=True)
class EntradaCambioContrasena:
    contrasena_actual: str
    contrasena_nueva: str


@dataclass(frozen=True, slots=True)
class SesionIniciada:
    tokens: ParDeTokens
    usuario: Usuario
    debe_cambiar_contrasena: bool = False


@dataclass(frozen=True, slots=True)
class PerfilUsuario:
    usuario: Usuario
    permisos: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Emision de sesion (compartido por las tres vias)
# ---------------------------------------------------------------------------


class _EmisorSesion:
    """Colaborador interno: valida el estado de la cuenta y emite los tokens.

    Se extrae como clase propia para que las tres vias de acceso compartan la
    misma implementacion. Si mañana se agrega un IdP, hereda estas reglas gratis.
    """

    def __init__(
        self,
        *,
        tokens: ServicioTokens,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._tokens = tokens
        self._reloj = reloj
        self._politica = politica

    async def emitir(
        self,
        usuario: Usuario,
        uow: UnidadDeTrabajo,
        contexto: ContextoEjecucion,
    ) -> SesionIniciada:
        ahora = self._reloj.ahora()
        usuario.asegurar_puede_iniciar_sesion(ahora)

        acceso, expira = self._tokens.emitir_acceso(
            ContenidoToken(
                usuario_id=usuario.id,
                email=str(usuario.email),
                permisos=frozenset(p.value for p in usuario.permisos),
            )
        )
        refresco, hash_refresco, expira_refresco = self._tokens.emitir_refresco(usuario.id)

        await uow.tokens.agregar(
            TokenRefresco(
                usuario_id=usuario.id,
                hash_token=hash_refresco,
                expira_en=expira_refresco,
                user_agent=contexto.user_agent,
                direccion_ip=contexto.direccion_ip,
            )
        )

        usuario.registrar_acceso_exitoso(ahora)
        await uow.usuarios.actualizar(usuario)

        return SesionIniciada(
            tokens=ParDeTokens(
                acceso=acceso,
                refresco=refresco,
                expira_en_segundos=int((expira - ahora).total_seconds()),
            ),
            usuario=usuario,
            debe_cambiar_contrasena=usuario.debe_cambiar_contrasena,
        )


# ---------------------------------------------------------------------------
# Inicio de sesion local
# ---------------------------------------------------------------------------


class IniciarSesion(CasoDeUso[EntradaInicioSesion, SesionIniciada]):
    """Autentica con correo y contrasena locales."""

    nombre = "auth.iniciar_sesion"
    descripcion = "Autentica a un usuario con credenciales locales"
    permiso_requerido = None

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        hasher: HasherContrasenas,
        tokens: ServicioTokens,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._reloj = reloj
        self._politica = politica
        self._emisor = _EmisorSesion(tokens=tokens, reloj=reloj, politica=politica)

    async def _ejecutar(
        self, entrada: EntradaInicioSesion, contexto: ContextoEjecucion
    ) -> SesionIniciada:
        try:
            email = Email(entrada.email)
        except ErrorValidacion:
            # Un correo malformado se responde igual que uno inexistente: no se
            # revela si la cuenta existe.
            raise CredencialesInvalidas from None

        async with self._uow:
            usuario = await self._uow.usuarios.obtener_por_email(email)

            if usuario is None:
                # Se consume el mismo coste de trabajo aunque la cuenta no
                # exista: de lo contrario, el tiempo de respuesta revelaria que
                # correos estan registrados (ataque por temporizacion).
                self._hasher.hashear(entrada.contrasena)
                raise CredencialesInvalidas

            usuario.asegurar_puede_iniciar_sesion(self._reloj.ahora())

            if not usuario.usa_credencial_local:
                raise ConflictoDeEstado(
                    f"Esta cuenta se autentica mediante {usuario.proveedor.value}. "
                    "Use esa via de acceso."
                )

            assert usuario.hash_contrasena is not None
            if not self._hasher.verificar(entrada.contrasena, usuario.hash_contrasena):
                usuario.registrar_intento_fallido(
                    maximo=self._politica.max_intentos_fallidos,
                    minutos_bloqueo=self._politica.minutos_bloqueo,
                    ahora=self._reloj.ahora(),
                )
                await self._uow.usuarios.actualizar(usuario)
                await self._uow.commit()
                raise CredencialesInvalidas

            # Si el coste de trabajo subio desde el ultimo acceso, se rehashea
            # aprovechando que aqui tenemos la contrasena en claro.
            if self._hasher.necesita_rehash(usuario.hash_contrasena):
                usuario.hash_contrasena = self._hasher.hashear(entrada.contrasena)

            sesion = await self._emisor.emitir(usuario, self._uow, contexto)
            await self._uow.commit()
            return sesion


# ---------------------------------------------------------------------------
# Inicio de sesion federado (Google / LDAP)
# ---------------------------------------------------------------------------


class IniciarSesionFederado(CasoDeUso[EntradaInicioFederado, SesionIniciada]):
    """Autentica contra un proveedor externo y aprovisiona la cuenta local.

    El aprovisionamiento automatico es deliberado: el usuario ya fue validado
    por un sistema de confianza institucional, y obligarlo a esperar la creacion
    manual de una cuenta no aporta seguridad. Lo que si se controla es el rol —
    entra siempre con el minimo (`CONSULTA`) y un administrador lo eleva.
    """

    nombre = "auth.iniciar_sesion_federado"
    descripcion = "Autentica mediante Google o directorio activo"
    permiso_requerido = None

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        proveedores: dict[AuthProvider, ProveedorIdentidad],
        tokens: ServicioTokens,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._uow = uow
        self._proveedores = proveedores
        self._reloj = reloj
        self._politica = politica
        self._emisor = _EmisorSesion(tokens=tokens, reloj=reloj, politica=politica)

    async def _ejecutar(
        self, entrada: EntradaInicioFederado, contexto: ContextoEjecucion
    ) -> SesionIniciada:
        proveedor = self._proveedores.get(entrada.proveedor)
        if proveedor is None or not proveedor.esta_habilitado:
            raise ProveedorNoHabilitado(entrada.proveedor.value)

        identidad = await proveedor.autenticar(entrada.credencial, entrada.secreto)

        async with self._uow:
            usuario = await self._resolver_usuario(identidad)
            sesion = await self._emisor.emitir(usuario, self._uow, contexto)
            await self._uow.commit()
            return sesion

    async def _resolver_usuario(self, identidad: IdentidadExterna) -> Usuario:
        """Localiza la cuenta por identificador externo, luego por correo.

        El identificador externo tiene prioridad porque es estable: si a una
        persona le cambian el correo institucional, sigue siendo la misma cuenta.
        """
        usuario = await self._uow.usuarios.obtener_por_externo(
            identidad.proveedor.value, identidad.identificador
        )
        if usuario is not None:
            await self._sincronizar(usuario, identidad)
            return usuario

        email = Email(identidad.email)
        usuario = await self._uow.usuarios.obtener_por_email(email)
        if usuario is not None:
            if usuario.proveedor is AuthProvider.LOCAL:
                # Cuenta local preexistente con el mismo correo: se vincula la
                # identidad externa en lugar de crear un duplicado.
                usuario.proveedor = identidad.proveedor
                usuario.identificador_externo = identidad.identificador
            elif usuario.identificador_externo != identidad.identificador:
                raise CredencialesInvalidas("El correo ya esta asociado a otra identidad externa")
            await self._sincronizar(usuario, identidad)
            return usuario

        return await self._aprovisionar(identidad, email)

    async def _sincronizar(self, usuario: Usuario, identidad: IdentidadExterna) -> None:
        if identidad.nombre_completo and usuario.nombre_completo != identidad.nombre_completo:
            usuario.nombre_completo = identidad.nombre_completo
        if usuario.identificador_externo is None:
            usuario.identificador_externo = identidad.identificador
        await self._uow.usuarios.actualizar(usuario)

    async def _aprovisionar(self, identidad: IdentidadExterna, email: Email) -> Usuario:
        rol = await self._uow.roles.obtener_por_codigo(self._politica.rol_por_defecto_federado)
        if rol is None:
            raise NoEncontrado("Rol por defecto", self._politica.rol_por_defecto_federado)

        usuario = Usuario(
            email=email,
            nombre_completo=identidad.nombre_completo or email.usuario,
            proveedor=identidad.proveedor,
            identificador_externo=identidad.identificador,
            roles={rol},
            activo=True,
        )
        return await self._uow.usuarios.agregar(usuario)


# ---------------------------------------------------------------------------
# Refresco y cierre de sesion
# ---------------------------------------------------------------------------


class RefrescarSesion(CasoDeUso[EntradaRefresco, SesionIniciada]):
    """Canjea un token de refresco por un par nuevo, rotandolo.

    La rotacion incluye deteccion de reutilizacion: si llega un token que ya fue
    canjeado, se asume robo y se revocan **todas** las sesiones del usuario. Es
    agresivo a proposito — ante la duda, se prefiere obligar a reautenticar.
    """

    nombre = "auth.refrescar_sesion"
    descripcion = "Renueva el par de tokens a partir de un token de refresco"
    permiso_requerido = None

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        tokens: ServicioTokens,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._reloj = reloj
        self._emisor = _EmisorSesion(tokens=tokens, reloj=reloj, politica=politica)

    async def _ejecutar(
        self, entrada: EntradaRefresco, contexto: ContextoEjecucion
    ) -> SesionIniciada:
        hash_token = self._tokens.hash_de_refresco(entrada.token_refresco)

        async with self._uow:
            almacenado = await self._uow.tokens.obtener_por_hash(hash_token)
            if almacenado is None:
                raise TokenInvalido

            if almacenado.esta_revocado:
                revocados = await self._uow.tokens.revocar_todos_de(almacenado.usuario_id)
                await self._uow.commit()
                raise TokenInvalido(
                    "Se detecto reutilizacion de un token revocado. "
                    f"Se cerraron {revocados} sesion(es) por seguridad."
                )

            if not almacenado.es_utilizable(self._reloj.ahora()):
                raise TokenInvalido

            usuario = await self._uow.usuarios.obtener(almacenado.usuario_id)
            if usuario is None:
                raise TokenInvalido
            if not usuario.activo:
                raise UsuarioInactivo

            sesion = await self._emisor.emitir(usuario, self._uow, contexto)
            almacenado.revocar()
            await self._uow.tokens.actualizar(almacenado)
            await self._uow.commit()
            return sesion


class CerrarSesion(CasoDeUso[EntradaRefresco, None]):
    """Revoca el token de refresco de la sesion actual."""

    nombre = "auth.cerrar_sesion"
    descripcion = "Cierra la sesion revocando su token de refresco"
    permiso_requerido = None

    def __init__(self, uow: UnidadDeTrabajo, tokens: ServicioTokens) -> None:
        self._uow = uow
        self._tokens = tokens

    async def _ejecutar(self, entrada: EntradaRefresco, contexto: ContextoEjecucion) -> None:
        hash_token = self._tokens.hash_de_refresco(entrada.token_refresco)
        async with self._uow:
            almacenado = await self._uow.tokens.obtener_por_hash(hash_token)
            # Cerrar una sesion inexistente no es un error: el efecto deseado
            # —que ese token no sirva— ya se cumple.
            if almacenado is not None and not almacenado.esta_revocado:
                almacenado.revocar()
                await self._uow.tokens.actualizar(almacenado)
                await self._uow.commit()


class CerrarTodasLasSesiones(CasoDeUso[UUID, int]):
    """Revoca todas las sesiones de un usuario. Devuelve cuantas cerro."""

    nombre = "auth.cerrar_todas_las_sesiones"
    descripcion = "Revoca todos los tokens de refresco de un usuario"
    permiso_requerido = None

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> int:
        # Solo el propio usuario, o quien administre usuarios, puede hacerlo.
        actor = contexto.actor
        if actor is None:
            raise TokenInvalido
        if actor.id != entrada and not actor.puede(Permiso.USUARIOS_ESCRIBIR):
            from app.domain.errors import ErrorAutorizacion

            raise ErrorAutorizacion(Permiso.USUARIOS_ESCRIBIR.value)

        async with self._uow:
            total = await self._uow.tokens.revocar_todos_de(entrada)
            await self._uow.commit()
            return total


# ---------------------------------------------------------------------------
# Contrasena y perfil
# ---------------------------------------------------------------------------


class CambiarContrasenaPropia(CasoDeUso[EntradaCambioContrasena, None]):
    """Cambia la contrasena del usuario autenticado.

    Al cambiarla se revocan las demas sesiones: si el motivo del cambio es una
    sospecha de compromiso, dejar vivas las sesiones abiertas anularia el gesto.
    """

    nombre = "auth.cambiar_contrasena"
    descripcion = "Cambia la contrasena de la cuenta propia"
    permiso_requerido = None

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        hasher: HasherContrasenas,
        politica: PoliticaAcceso,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._politica = politica

    async def _ejecutar(
        self, entrada: EntradaCambioContrasena, contexto: ContextoEjecucion
    ) -> None:
        if contexto.actor is None:
            raise TokenInvalido

        async with self._uow:
            usuario = await self._uow.usuarios.obtener(contexto.actor.id)
            if usuario is None:
                raise NoEncontrado("Usuario", contexto.actor.id)
            if not usuario.usa_credencial_local:
                raise ConflictoDeEstado(
                    f"La cuenta se autentica por {usuario.proveedor.value}; "
                    "la contrasena se gestiona en ese sistema"
                )

            assert usuario.hash_contrasena is not None
            if not self._hasher.verificar(entrada.contrasena_actual, usuario.hash_contrasena):
                raise CredencialesInvalidas("La contrasena actual no es correcta")

            if entrada.contrasena_actual == entrada.contrasena_nueva:
                raise ErrorValidacion(
                    "La contrasena nueva debe ser distinta de la actual", campo="password"
                )

            nueva = ContrasenaEnClaro(
                entrada.contrasena_nueva,
                longitud_minima=self._politica.longitud_minima_contrasena,
            )
            usuario.establecer_hash(self._hasher.hashear(nueva.valor))
            await self._uow.usuarios.actualizar(usuario)
            await self._uow.tokens.revocar_todos_de(usuario.id)
            await self._uow.commit()


class ObtenerPerfil(CasoDeUso[None, PerfilUsuario]):
    """Devuelve el usuario autenticado con sus permisos efectivos.

    El frontend lo consume al arrancar para decidir que menus y acciones mostrar.
    """

    nombre = "auth.perfil"
    descripcion = "Datos y permisos del usuario autenticado"
    permiso_requerido = None

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> PerfilUsuario:
        if contexto.actor is None:
            raise TokenInvalido
        async with self._uow:
            usuario = await self._uow.usuarios.obtener(contexto.actor.id)
            if usuario is None:
                raise NoEncontrado("Usuario", contexto.actor.id)
            return PerfilUsuario(
                usuario=usuario,
                permisos=sorted(p.value for p in usuario.permisos),
            )


class LimpiarTokensExpirados(CasoDeUso[None, int]):
    """Tarea de mantenimiento: borra tokens de refresco vencidos."""

    nombre = "auth.limpiar_tokens"
    descripcion = "Elimina los tokens de refresco expirados"
    permiso_requerido = None

    def __init__(self, uow: UnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = uow
        self._reloj = reloj

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> int:
        async with self._uow:
            # Se conservan 30 dias tras la expiracion por trazabilidad forense.
            corte = self._reloj.ahora() - timedelta(days=30)
            eliminados = await self._uow.tokens.eliminar_expirados(corte)
            await self._uow.commit()
            return eliminados
