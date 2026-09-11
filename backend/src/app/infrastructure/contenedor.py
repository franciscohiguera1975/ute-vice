"""Contenedor de dependencias.

Es el unico lugar donde se decide que implementacion concreta cumple cada
puerto. Los casos de uso reciben sus colaboradores ya construidos y no invocan
nunca a una fabrica: eso es inversion de dependencias con inyeccion explicita,
sin magia ni decoradores.

Division deliberada:

* **Singletons** (motor, hasher, tokens, proveedor, exportadores, politica):
  se construyen una vez por proceso porque son caros o no tienen estado por
  peticion.
* **Por peticion** (unidad de trabajo y, con ella, los repositorios): una
  transaccion por peticion, cerrada al terminar.
"""

from __future__ import annotations

from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.casos_uso.autenticacion import PoliticaAcceso
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import AuthProvider
from app.domain.ports.analitica import RepositorioAnalitica
from app.domain.ports.reloj import (
    AleatorioDelSistema,
    FuenteAleatoria,
    Reloj,
    RelojDelSistema,
)
from app.domain.ports.reportes import RegistroExportadores
from app.domain.ports.seguridad import (
    HasherContrasenas,
    ProveedorIdentidad,
    ServicioTokens,
)
from app.domain.ports.senescyt import ProveedorConsultaTitulos
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.services.planificacion import ConfiguracionRitmo, PoliticaPlanificacion
from app.domain.services.reconciliador import ReconciliadorTitulos
from app.infrastructure.db.analitica import RepositorioAnaliticaSQL
from app.infrastructure.db.sesion import crear_fabrica_sesiones, crear_motor
from app.infrastructure.db.uow import UnidadDeTrabajoSQL
from app.infrastructure.reportes.registro import RegistroExportadoresEnMemoria
from app.infrastructure.seguridad.google import ProveedorGoogle
from app.infrastructure.seguridad.hasher import HasherArgon2
from app.infrastructure.seguridad.ldap import ProveedorLDAP
from app.infrastructure.seguridad.tokens import ServicioTokensJWT
from app.infrastructure.senescyt.fabrica import crear_proveedor
from app.infrastructure.senescyt.manual import ConfiguracionPortal

log = get_logger(__name__)


class Contenedor:
    """Raiz de composicion de la aplicacion."""

    def __init__(
        self,
        settings: Settings,
        *,
        portal_senescyt: ConfiguracionPortal | None = None,
    ) -> None:
        self.settings = settings
        self._portal = portal_senescyt

    # ------------------------------------------------------ infraestructura
    @cached_property
    def motor(self) -> AsyncEngine:
        return crear_motor(self.settings.db)

    @cached_property
    def fabrica_sesiones(self) -> async_sessionmaker[AsyncSession]:
        return crear_fabrica_sesiones(self.motor)

    def unidad_de_trabajo(self) -> UnidadDeTrabajo:
        """Nueva unidad de trabajo. Una por peticion o por tarea."""
        return UnidadDeTrabajoSQL(self.fabrica_sesiones)

    def analitica(self, sesion: AsyncSession) -> RepositorioAnalitica:
        return RepositorioAnaliticaSQL(sesion)

    # -------------------------------------------------------------- tiempo
    @cached_property
    def reloj(self) -> Reloj:
        return RelojDelSistema(zona_local=self.settings.tz)

    @cached_property
    def aleatorio(self) -> FuenteAleatoria:
        return AleatorioDelSistema()

    # ----------------------------------------------------------- seguridad
    @cached_property
    def hasher(self) -> HasherContrasenas:
        return HasherArgon2()

    @cached_property
    def tokens(self) -> ServicioTokens:
        return ServicioTokensJWT(self.settings.jwt)

    @cached_property
    def politica_acceso(self) -> PoliticaAcceso:
        seguridad = self.settings.security
        return PoliticaAcceso(
            max_intentos_fallidos=seguridad.max_failed_logins,
            minutos_bloqueo=seguridad.lockout_minutes,
            dias_refresco=self.settings.jwt.refresh_token_expire_days,
            longitud_minima_contrasena=seguridad.password_min_length,
            rol_por_defecto_federado=self.settings.google.default_role,
        )

    @cached_property
    def proveedor_google(self) -> ProveedorGoogle:
        return ProveedorGoogle(self.settings.google)

    @cached_property
    def proveedor_ldap(self) -> ProveedorLDAP:
        return ProveedorLDAP(self.settings.ldap)

    @cached_property
    def proveedores_identidad(self) -> dict[AuthProvider, ProveedorIdentidad]:
        """Todos los proveedores federados, indexados por tipo.

        Se registran aunque esten deshabilitados: es el propio proveedor quien
        responde `ProveedorNoHabilitado`, con un mensaje util, en lugar de que
        el caso de uso reciba un diccionario incompleto y falle con un
        `KeyError` incomprensible.
        """
        return {
            AuthProvider.GOOGLE: self.proveedor_google,
            AuthProvider.LDAP: self.proveedor_ldap,
        }

    # ------------------------------------------------------------ consultas
    @cached_property
    def proveedor_titulos(self) -> ProveedorConsultaTitulos:
        return crear_proveedor(self.settings.senescyt, portal=self._portal)

    @cached_property
    def reconciliador(self) -> ReconciliadorTitulos:
        return ReconciliadorTitulos(marcar_ausentes_como_retirados=True)

    @cached_property
    def configuracion_ritmo(self) -> ConfiguracionRitmo:
        cfg = self.settings.scheduler
        return ConfiguracionRitmo(
            periodo_dias=cfg.period_days,
            max_consultas_por_hora=cfg.max_requests_per_hour,
            hora_inicio_pico=cfg.peak_start_hour,
            hora_fin_pico=cfg.peak_end_hour,
            hora_fin_valle=cfg.offpeak_end_hour,
            peso_pico=cfg.peak_weight,
            peso_valle=cfg.offpeak_weight,
            demora_minima_segundos=cfg.min_delay_seconds,
            demora_maxima_segundos=cfg.max_delay_seconds,
            retroceso_base_segundos=cfg.backoff_base_seconds,
            retroceso_maximo_segundos=cfg.backoff_max_seconds,
            umbral_cortacircuitos=cfg.circuit_breaker_failures,
            max_intentos_por_persona=self.settings.senescyt.max_attempts,
        )

    @cached_property
    def politica_planificacion(self) -> PoliticaPlanificacion:
        return PoliticaPlanificacion(self.configuracion_ritmo, self.aleatorio)

    # ------------------------------------------------------------- reportes
    @cached_property
    def exportadores(self) -> RegistroExportadores:
        return RegistroExportadoresEnMemoria()

    # ------------------------------------------------------------- apagado
    async def cerrar(self) -> None:
        """Libera recursos al apagar la aplicacion."""
        try:
            await self.proveedor_titulos.cerrar()
        except Exception:
            log.warning("Fallo al cerrar el proveedor de consultas", exc_info=True)

        if "motor" in self.__dict__:
            await self.motor.dispose()

    def resumen_configuracion(self) -> dict[str, object]:
        """Configuracion efectiva, sin secretos. Se registra al arrancar."""
        cfg = self.settings
        return {
            "entorno": cfg.environment.value,
            "base_datos": f"{cfg.db.host}:{cfg.db.port}/{cfg.db.db}",
            "proveedor_senescyt": cfg.senescyt.provider.value,
            "google_oauth": cfg.google.enabled,
            "ldap": cfg.ldap.enabled,
            "planificador": cfg.scheduler.enabled,
            "periodo_cobertura_dias": cfg.scheduler.period_days,
            "consultas_por_hora": cfg.scheduler.max_requests_per_hour,
            "franja_pico": (
                f"{cfg.scheduler.peak_start_hour:02d}:00-{cfg.scheduler.peak_end_hour:02d}:00"
            ),
            "franja_valle": (
                f"{cfg.scheduler.peak_end_hour:02d}:00-{cfg.scheduler.offpeak_end_hour:02d}:00"
            ),
            "capacidad_diaria_estimada": (
                self.politica_planificacion.consultas_diarias_estimadas()
            ),
        }
