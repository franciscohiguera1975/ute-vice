"""Ejecutor en segundo plano de los jobs de cobertura.

Es un bucle deliberadamente simple: pregunta al caso de uso `AvanzarJob` que
hacer, espera lo que este le indique, y repite. Toda la inteligencia —franja
horaria, presupuesto, retroceso, cortacircuitos— vive en el dominio, no aqui.
Este modulo solo aporta el hilo de ejecucion y la resistencia a fallos.

Propiedades que importan para una campana que dura dias:

* **Reanudable.** El estado vive en la base, no en memoria. Si el contenedor se
  reinicia, el bucle vuelve a arrancar y retoma en el mismo item.
* **Un solo trabajador por instancia.** La exclusion real la da
  `FOR UPDATE SKIP LOCKED` en la base, asi que varias replicas tampoco se pisan.
* **Cancelable.** Responde a la senal de apagado sin dejar transacciones a medias.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.application.base import ContextoEjecucion
from app.application.casos_uso.consultas import AvanzarJob, PasoJob
from app.core.logging import get_logger
from app.domain.enums import EstadoJob
from app.domain.ports.uow import UnidadDeTrabajo

log = get_logger(__name__)

#: Espera cuando no hay ningun job activo que atender.
_ESPERA_SIN_JOB = 60.0

#: Tope de espera por iteracion. Evita dormir horas de una sola vez y permite
#: que el apagado responda en un plazo razonable.
_ESPERA_MAXIMA = 300.0


class EjecutorPlanificador:
    """Bucle que hace avanzar el job activo."""

    def __init__(
        self,
        *,
        fabrica_avanzar: Callable[[], AvanzarJob],
        uow: UnidadDeTrabajo,
        habilitado: bool = False,
    ) -> None:
        self._fabrica_avanzar = fabrica_avanzar
        self._uow = uow
        self._habilitado = habilitado
        self._tarea: asyncio.Task[None] | None = None
        self._detener = asyncio.Event()
        self._ultimo_paso: PasoJob | None = None

    # ------------------------------------------------------- ciclo de vida
    async def iniciar(self) -> None:
        if not self._habilitado:
            log.info(
                "Planificador deshabilitado (SCHEDULER_ENABLED=false). "
                "Los jobs solo avanzaran si se invoca el endpoint manualmente."
            )
            return
        if self._tarea is not None and not self._tarea.done():
            return

        self._detener.clear()
        self._tarea = asyncio.create_task(self._bucle(), name="planificador-consultas")
        log.info("Planificador de consultas iniciado")

    async def detener(self, *, espera_maxima: float = 15.0) -> None:
        if self._tarea is None:
            return
        self._detener.set()
        try:
            await asyncio.wait_for(self._tarea, timeout=espera_maxima)
        except TimeoutError:
            log.warning("El planificador no se detuvo a tiempo; se cancela")
            self._tarea.cancel()
            with_suppress = asyncio.gather(self._tarea, return_exceptions=True)
            await with_suppress
        finally:
            self._tarea = None
            log.info("Planificador de consultas detenido")

    @property
    def esta_activo(self) -> bool:
        return self._tarea is not None and not self._tarea.done()

    @property
    def ultimo_paso(self) -> PasoJob | None:
        """Ultimo resultado, para exponerlo en el endpoint de estado."""
        return self._ultimo_paso

    # ------------------------------------------------------------- bucle
    async def _bucle(self) -> None:
        fallos_seguidos = 0

        while not self._detener.is_set():
            try:
                espera = await self._iterar()
                fallos_seguidos = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                fallos_seguidos += 1
                # Retroceso ante fallos del propio ejecutor (no del proveedor):
                # tipicamente, la base de datos no disponible.
                espera = min(30.0 * 2 ** min(fallos_seguidos - 1, 5), _ESPERA_MAXIMA)
                log.exception(
                    "Error en el bucle del planificador; se reintentara",
                    extra={"espera_segundos": espera, "fallos_seguidos": fallos_seguidos},
                )

            await self._dormir(min(espera, _ESPERA_MAXIMA))

    async def _iterar(self) -> float:
        """Una vuelta del bucle. Devuelve cuantos segundos esperar."""
        job_id = await self._job_activo()
        if job_id is None:
            return _ESPERA_SIN_JOB

        avanzar = self._fabrica_avanzar()
        paso = await avanzar(job_id, ContextoEjecucion.sistema())
        self._ultimo_paso = paso

        if paso.hubo_consulta and paso.resultado is not None:
            registro = paso.resultado.log
            log.info(
                "Consulta procesada",
                extra={
                    "job_id": str(job_id),
                    "cedula": registro.cedula.enmascarada(),
                    "estado": registro.estado.value,
                    "resumen": registro.resumen,
                    "proxima_en_s": paso.esperar_segundos,
                },
            )
        elif not paso.job_completado:
            log.debug(
                "Sin consulta en esta iteracion",
                extra={"motivo": paso.motivo, "espera_s": paso.esperar_segundos},
            )

        if paso.job_completado:
            log.info("Job de cobertura completado", extra={"job_id": str(job_id)})
            return _ESPERA_SIN_JOB

        if paso.job_pausado:
            log.warning(
                "El job quedo pausado; requiere intervencion",
                extra={"job_id": str(job_id), "motivo": paso.motivo},
            )
            return _ESPERA_SIN_JOB

        return float(paso.esperar_segundos)

    async def _job_activo(self) -> UUID | None:
        async with self._uow:
            job = await self._uow.jobs.job_activo()
        if job is None or job.estado is not EstadoJob.EN_CURSO:
            return None
        return job.id

    async def _dormir(self, segundos: float) -> None:
        """Espera interrumpible: el apagado no tiene que aguardar el intervalo."""
        if segundos <= 0:
            return
        # Agotar el tiempo es el caso normal: significa que nadie pidio apagar.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._detener.wait(), timeout=segundos)


def ahora() -> datetime:
    return datetime.now(UTC)
