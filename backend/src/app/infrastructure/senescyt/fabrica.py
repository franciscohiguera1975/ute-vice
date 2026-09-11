"""Seleccion del proveedor de consulta segun la configuracion.

Es el unico punto del sistema que conoce las tres implementaciones. El resto
—casos de uso, planificador, API— solo ve el puerto `ProveedorConsultaTitulos`.
Cambiar de proveedor es cambiar una variable de entorno.
"""

from __future__ import annotations

from app.core.config import SenescytProviderKind, SenescytSettings
from app.core.logging import get_logger
from app.domain.ports.senescyt import ProveedorConsultaTitulos
from app.infrastructure.senescyt.manual import ConfiguracionPortal, ProveedorManual
from app.infrastructure.senescyt.mock import ProveedorMock
from app.infrastructure.senescyt.oficial import ProveedorOficial

log = get_logger(__name__)


def crear_proveedor(
    config: SenescytSettings,
    *,
    portal: ConfiguracionPortal | None = None,
) -> ProveedorConsultaTitulos:
    """Construye el proveedor indicado por `SENESCYT_PROVIDER`."""
    match config.provider:
        case SenescytProviderKind.MOCK:
            log.info("Proveedor SENESCYT: mock (datos simulados). No apto para produccion.")
            return ProveedorMock()

        case SenescytProviderKind.MANUAL:
            configuracion = portal or ConfiguracionPortal()
            if not configuracion.esta_configurado:
                log.warning(
                    "Proveedor SENESCYT: manual, pero sin configuracion del portal. "
                    "Las consultas fallaran de forma explicita hasta completarla."
                )
            else:
                log.info(
                    "Proveedor SENESCYT: manual (resolucion humana del desafio de verificacion)."
                )
            return ProveedorManual(
                configuracion,
                base_url=config.base_url,
                timeout_segundos=config.timeout_seconds,
            )

        case SenescytProviderKind.OFICIAL:
            log.info("Proveedor SENESCYT: API institucional bajo convenio.")
            return ProveedorOficial(
                url_base=config.oficial_api_url,
                api_key=config.oficial_api_key,
                timeout_segundos=config.timeout_seconds,
            )

    raise ValueError(f"Proveedor no soportado: {config.provider}")
