"""Casos de uso de consulta al registro nacional de titulos.

Este modulo implementa el proceso pedido: recorrer el padron de personas,
consultar los titulos de cada una por su cedula, y dejar constancia en el
historico de todo lo que ocurra —cambios, ausencias de datos y errores—.

Piezas y responsabilidades:

* `EjecutorConsulta` — ejecuta *una* consulta de principio a fin. Es el unico
  sitio del sistema donde se llama al proveedor externo y se escribe en el
  historico. Tanto la consulta puntual como el job por lotes pasan por aqui, de
  modo que ambas producen exactamente el mismo rastro.
* `ConsultarPersona` — consulta puntual lanzada por un usuario.
* `CrearJobCobertura` — arma la campana que cubre todo el padron en un periodo.
* `AvanzarJob` — un paso del planificador. Se invoca repetidamente; cada
  llamada decide si toca consultar, a quien, y cuanto esperar despues.
* `ResolverDesafio` — recibe del operador la respuesta al desafio de
  verificacion y reanuda la consulta que quedo en espera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.core.logging import get_logger
from app.domain.entities.consulta import ConsultaLog, ItemJob, JobCobertura
from app.domain.entities.persona import Persona
from app.domain.enums import (
    EstadoConsulta,
    EstadoItemJob,
    EstadoJob,
    Permiso,
)
from app.domain.errors import (
    ConflictoDeEstado,
    NoEncontrado,
    ReglaDeNegocioViolada,
)
from app.domain.ports.reloj import FuenteAleatoria, Reloj
from app.domain.ports.repositorios import FiltroLogs, Pagina, Paginacion
from app.domain.ports.senescyt import ProveedorConsultaTitulos, ResultadoConsulta
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.services.planificacion import (
    DecisionRitmo,
    EvaluacionFactibilidad,
    PoliticaPlanificacion,
)
from app.domain.services.reconciliador import ReconciliadorTitulos
from app.domain.value_objects import PeriodoCobertura

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResultadoEjecucion:
    """Resultado de una consulta individual, ya persistido."""

    log: ConsultaLog
    persona: Persona
    desafio_id: str | None = None
    resumen_cambios: dict[str, int] = field(default_factory=dict)

    @property
    def requiere_intervencion(self) -> bool:
        return self.log.estado is EstadoConsulta.DESAFIO_PENDIENTE


@dataclass(frozen=True, slots=True)
class DesafioPendiente:
    """Desafio a la espera de que un operador lo resuelva."""

    desafio_id: str
    persona_id: UUID
    cedula_enmascarada: str
    nombre_persona: str
    tipo: str
    imagen_base64: str | None
    instruccion: str
    expira_en_segundos: int


@dataclass(frozen=True, slots=True)
class PasoJob:
    """Lo que ocurrio en un paso del planificador."""

    job_id: UUID
    hubo_consulta: bool
    esperar_segundos: int
    motivo: str
    resultado: ResultadoEjecucion | None = None
    job_completado: bool = False
    job_pausado: bool = False


# ---------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaConsultarPersona:
    persona_id: UUID
    forzar: bool = False
    """Ignora la regla de cobertura del periodo. Requiere justificacion."""


@dataclass(frozen=True, slots=True)
class EntradaCrearJob:
    nombre: str
    periodo_dias: int | None = None
    limite_personas: int | None = None
    """Acota el job a las N personas mas prioritarias. Util para pruebas."""
    iniciar_inmediatamente: bool = False
    distribuir_en_periodo: bool = False
    """Reparte los items a lo largo del periodo en lugar de encolarlos ya.

    Por defecto esta desactivado: el ritmo lo impone la politica de
    planificacion (jitter, presupuesto por hora y franja horaria), y anadir un
    segundo mecanismo de espera solo consigue que una campana pequena tarde
    dias en avanzar sin ninguna ganancia. Actívelo si prefiere que la frescura
    del dato se reparta de forma uniforme durante todo el periodo en lugar de
    concentrarse al principio.
    """


@dataclass(frozen=True, slots=True)
class EntradaResolverDesafio:
    desafio_id: str
    respuesta: str


@dataclass(frozen=True, slots=True)
class EntradaControlJob:
    job_id: UUID
    accion: str
    """`iniciar`, `pausar`, `reanudar` o `cancelar`."""
    motivo: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaListarLogs:
    filtro: FiltroLogs = field(default_factory=FiltroLogs)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class JobCreado:
    job: JobCobertura
    factibilidad: EvaluacionFactibilidad
    advertencia: str | None = None


# ---------------------------------------------------------------------------
# Ejecutor: el corazon del proceso
# ---------------------------------------------------------------------------


class EjecutorConsulta:
    """Ejecuta una consulta completa y deja el historico consistente.

    Garantia central: **siempre** se escribe una fila en `consulta_logs`, sin
    importar como termine la operacion. Un error de red, un rechazo del
    proveedor o una cedula que ya no valida producen su registro igual que un
    exito. Sin esa garantia, un dato desactualizado seria indistinguible de un
    dato que nunca se pudo consultar.

    No es un caso de uso: es un colaborador que varios casos de uso comparten.
    Por eso no lleva permiso propio — lo autoriza quien lo invoca.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        proveedor: ProveedorConsultaTitulos,
        reconciliador: ReconciliadorTitulos,
        reloj: Reloj,
    ) -> None:
        self._uow = uow
        self._proveedor = proveedor
        self._reconciliador = reconciliador
        self._reloj = reloj

    async def ejecutar(
        self,
        persona: Persona,
        *,
        job_id: UUID | None = None,
        intento: int = 1,
        ejecutado_por: UUID | None = None,
    ) -> ResultadoEjecucion:
        registro = ConsultaLog.iniciar(
            persona_id=persona.id,
            cedula=persona.cedula,
            proveedor=self._proveedor.nombre,
            job_id=job_id,
            intento=intento,
            ejecutado_por=ejecutado_por,
        )

        try:
            respuesta = await self._proveedor.consultar(persona.cedula)
        except Exception as exc:
            log.exception(
                "Fallo inesperado al consultar el proveedor",
                extra={"persona_id": str(persona.id), "proveedor": self._proveedor.nombre},
            )
            registro.cerrar_con_error(
                EstadoConsulta.ERROR_PROVEEDOR,
                mensaje=str(exc),
                tipo_error=type(exc).__name__,
                momento=self._reloj.ahora(),
            )
            return await self._persistir(registro, persona)

        return await self._procesar(registro, persona, respuesta)

    async def reanudar_con_respuesta(
        self,
        persona: Persona,
        *,
        desafio_id: str,
        respuesta_operador: str,
        contexto_desafio: dict[str, object],
        job_id: UUID | None = None,
        ejecutado_por: UUID | None = None,
    ) -> ResultadoEjecucion:
        """Retoma una consulta que quedo esperando verificacion humana."""
        registro = ConsultaLog.iniciar(
            persona_id=persona.id,
            cedula=persona.cedula,
            proveedor=self._proveedor.nombre,
            job_id=job_id,
            ejecutado_por=ejecutado_por,
        )
        try:
            respuesta = await self._proveedor.resolver_desafio(
                desafio_id, respuesta_operador, dict(contexto_desafio)
            )
        except Exception as exc:
            registro.cerrar_con_error(
                EstadoConsulta.ERROR_PROVEEDOR,
                mensaje=str(exc),
                tipo_error=type(exc).__name__,
                momento=self._reloj.ahora(),
            )
            return await self._persistir(registro, persona)

        return await self._procesar(registro, persona, respuesta)

    # ------------------------------------------------------------- internos
    async def _procesar(
        self, registro: ConsultaLog, persona: Persona, respuesta: ResultadoConsulta
    ) -> ResultadoEjecucion:
        ahora = self._reloj.ahora()

        # Caso 1: el proveedor pide verificacion humana. No es un fallo.
        if respuesta.requiere_intervencion and respuesta.desafio is not None:
            registro.cerrar_esperando_desafio(
                desafio_id=respuesta.desafio.desafio_id, momento=ahora
            )
            return await self._persistir(registro, persona, desafio_id=respuesta.desafio.desafio_id)

        # Caso 2: el proveedor reporto un error.
        if not respuesta.exitosa:
            registro.cerrar_con_error(
                self._clasificar(respuesta),
                mensaje=respuesta.mensaje or "El proveedor no completo la consulta",
                codigo_http=respuesta.codigo_http,
                momento=ahora,
            )
            return await self._persistir(registro, persona)

        # Caso 3: respuesta valida. Se reconcilia contra lo que ya teniamos.
        existentes = await self._uow.titulos.listar_por_persona(persona.id)
        plan = self._reconciliador.reconciliar(
            persona_id=persona.id,
            existentes=existentes,
            externos=respuesta.titulos,
            momento=ahora,
        )

        if plan.nuevos:
            await self._uow.titulos.agregar_muchos(plan.nuevos)
        modificados = plan.actualizados + plan.confirmados + plan.retirados
        if modificados:
            await self._uow.titulos.actualizar_muchos(modificados)

        registro.cerrar_con_exito(
            titulos_encontrados=len(respuesta.titulos),
            cambios=plan.cambios,
            respuesta_cruda=respuesta.respuesta_cruda or None,
            momento=ahora,
        )

        resultado = await self._persistir(
            registro,
            persona,
            titulos_totales=len(existentes) + len(plan.nuevos),
            resumen=plan.resumen(),
        )

        if plan.hubo_cambios:
            log.info(
                "Cambios detectados en el expediente academico",
                extra={
                    "persona_id": str(persona.id),
                    "cedula": persona.cedula.enmascarada(),
                    **plan.resumen(),
                },
            )
        return resultado

    async def _persistir(
        self,
        registro: ConsultaLog,
        persona: Persona,
        *,
        desafio_id: str | None = None,
        titulos_totales: int | None = None,
        resumen: dict[str, int] | None = None,
    ) -> ResultadoEjecucion:
        guardado = await self._uow.logs.agregar(registro)

        # El desafio pendiente no cuenta como consulta realizada: la persona
        # sigue sin dato y debe volver a intentarse.
        if registro.estado is not EstadoConsulta.DESAFIO_PENDIENTE:
            persona.registrar_consulta(
                registro.estado,
                momento=registro.finalizado_en,
                titulos_registrados=titulos_totales,
            )
            await self._uow.personas.actualizar(persona)

        return ResultadoEjecucion(
            log=guardado,
            persona=persona,
            desafio_id=desafio_id,
            resumen_cambios=resumen or {},
        )

    @staticmethod
    def _clasificar(respuesta: ResultadoConsulta) -> EstadoConsulta:
        """Traduce la respuesta del proveedor a un estado del historico.

        La distincion importa: `ERROR_DATOS` no reintenta ni abre el
        cortacircuitos, mientras que `RECHAZADO` detiene el job.
        """
        codigo = respuesta.codigo_http
        if codigo is None:
            return EstadoConsulta.ERROR_RED
        if codigo in {401, 403, 429}:
            return EstadoConsulta.RECHAZADO
        if codigo == 404:
            return EstadoConsulta.ERROR_DATOS
        if 500 <= codigo < 600:
            return EstadoConsulta.ERROR_PROVEEDOR
        if 400 <= codigo < 500:
            return EstadoConsulta.ERROR_DATOS
        return EstadoConsulta.ERROR_PROVEEDOR


# ---------------------------------------------------------------------------
# Consulta puntual
# ---------------------------------------------------------------------------


class ConsultarPersona(CasoDeUso[EntradaConsultarPersona, ResultadoEjecucion]):
    """Consulta los titulos de una persona concreta, bajo demanda.

    Respeta la regla de cobertura: si la persona ya fue consultada con exito en
    el periodo vigente, se rechaza salvo que se marque `forzar`. Esto evita que
    el uso manual erosione el reparto de carga que el planificador construyo.
    """

    nombre = "consultas.consultar_persona"
    descripcion = "Consulta al registro nacional los titulos de una persona"
    permiso_requerido = Permiso.CONSULTAS_EJECUTAR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        proveedor: ProveedorConsultaTitulos,
        reconciliador: ReconciliadorTitulos,
        reloj: Reloj,
        politica: PoliticaPlanificacion,
    ) -> None:
        self._uow = uow
        self._proveedor = proveedor
        self._reconciliador = reconciliador
        self._reloj = reloj
        self._politica = politica

    async def _ejecutar(
        self, entrada: EntradaConsultarPersona, contexto: ContextoEjecucion
    ) -> ResultadoEjecucion:
        ahora = self._reloj.ahora()

        async with self._uow:
            persona = await self._uow.personas.obtener(entrada.persona_id)
            if persona is None:
                raise NoEncontrado("Persona", entrada.persona_id)
            if not persona.activo:
                raise ReglaDeNegocioViolada("La persona esta inactiva; no se consultan sus titulos")

            if not entrada.forzar:
                periodo = PeriodoCobertura.desde(
                    ahora - timedelta(days=self._politica.configuracion.periodo_dias),
                    dias=self._politica.configuracion.periodo_dias,
                )
                if not persona.requiere_consulta(periodo, ahora=ahora):
                    raise ConflictoDeEstado(
                        "Esta persona ya fue consultada dentro del periodo vigente "
                        f"(ultima: {persona.ultima_consulta_en:%Y-%m-%d}). "
                        "Use la opcion de forzar si necesita repetirla."
                    )

            ejecutor = EjecutorConsulta(
                self._uow, self._proveedor, self._reconciliador, self._reloj
            )
            resultado = await ejecutor.ejecutar(persona, ejecutado_por=contexto.actor_id)
            await self._uow.commit()
            return resultado


# ---------------------------------------------------------------------------
# Jobs de cobertura
# ---------------------------------------------------------------------------


class CrearJobCobertura(CasoDeUso[EntradaCrearJob, JobCreado]):
    """Arma una campana que cubre el padron completo dentro de un periodo.

    El orden de la cola se baraja: recorrer el padron alfabeticamente o por
    fecha de alta concentraria la carga sobre grupos correlacionados. El barajado
    se aplica *dentro* de cada nivel de prioridad, de modo que quienes nunca han
    sido consultados siguen yendo primero.

    Antes de crear el job se evalua si el periodo alcanza para cubrir a todos. Si
    no alcanza, el job se crea igual pero con una advertencia explicita: la
    respuesta correcta es ampliar el periodo, nunca acelerar el ritmo.
    """

    nombre = "consultas.crear_job"
    descripcion = "Crea una campana de actualizacion sobre todo el padron"
    permiso_requerido = Permiso.CONSULTAS_ADMINISTRAR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        politica: PoliticaPlanificacion,
        reloj: Reloj,
        aleatorio: FuenteAleatoria,
    ) -> None:
        self._uow = uow
        self._politica = politica
        self._reloj = reloj
        self._rnd = aleatorio

    async def _ejecutar(self, entrada: EntradaCrearJob, contexto: ContextoEjecucion) -> JobCreado:
        ahora = self._reloj.ahora()
        dias = entrada.periodo_dias or self._politica.configuracion.periodo_dias
        periodo = PeriodoCobertura.desde(ahora, dias=dias)

        async with self._uow:
            if (activo := await self._uow.jobs.job_activo()) is not None:
                raise ConflictoDeEstado(
                    f"Ya existe un job activo ('{activo.nombre}', {activo.estado.value}). "
                    "Solo puede haber uno: dos campanas simultaneas romperian la "
                    "garantia de no repetir personas dentro del periodo."
                )

            candidatas = await self._uow.personas.seleccionar_para_cobertura(
                desde=periodo.inicio - timedelta(days=dias),
                hasta=ahora,
                limite=entrada.limite_personas,
            )
            if not candidatas:
                raise ConflictoDeEstado(
                    "No hay personas pendientes de consultar en este periodo. "
                    "La cobertura anterior ya esta completa."
                )

            candidatas.sort(key=lambda p: p.prioridad_consulta(ahora))
            items = self._construir_cola(
                candidatas, periodo, distribuir=entrada.distribuir_en_periodo
            )

            job = JobCobertura(
                nombre=entrada.nombre.strip(),
                periodo=periodo,
                creado_por=contexto.actor_id,
                configuracion=self._instantanea_configuracion(
                    dias, distribuir=entrada.distribuir_en_periodo
                ),
            )
            job.programar(total_items=len(items))

            guardado = await self._uow.jobs.agregar(job)
            await self._uow.jobs.agregar_items(
                [
                    ItemJob(job_id=guardado.id, persona_id=i[0], orden=i[1], programado_para=i[2])
                    for i in items
                ]
            )

            factibilidad = self._politica.evaluar_factibilidad(len(items))

            if entrada.iniciar_inmediatamente:
                guardado.iniciar(ahora)
                await self._uow.jobs.actualizar(guardado)

            await self._uow.commit()

            return JobCreado(
                job=guardado,
                factibilidad=factibilidad,
                advertencia=factibilidad.advertencia,
            )

    def _construir_cola(
        self,
        candidatas: list[Persona],
        periodo: PeriodoCobertura,
        *,
        distribuir: bool,
    ) -> list[tuple[UUID, int, datetime | None]]:
        """Ordena la cola: prioridad primero, azar dentro de cada nivel.

        El barajado importa. Recorrer el padron por orden alfabetico o por fecha
        de alta concentraria la carga sobre grupos correlacionados —una misma
        facultad, una misma promocion—, y si el proceso se interrumpe a medias,
        la cobertura quedaria sesgada en lugar de repartida.

        La marca `programado_para` solo se fija cuando se pide distribuir de
        forma explicita. En el modo normal se deja en `None` y todos los items
        quedan disponibles: quien impone el ritmo es la politica de
        planificacion, que ya aplica jitter, presupuesto horario y franja. Dos
        mecanismos de espera superpuestos no espacian mejor, solo bloquean.
        """
        por_nivel: dict[int, list[Persona]] = {}
        for persona in candidatas:
            nivel = persona.prioridad_consulta()[0]
            por_nivel.setdefault(nivel, []).append(persona)

        ordenadas: list[Persona] = []
        for nivel in sorted(por_nivel):
            grupo: list[object] = list(por_nivel[nivel])
            self._rnd.barajar(grupo)
            ordenadas.extend(grupo)  # type: ignore[arg-type]

        if not distribuir:
            return [(persona.id, indice, None) for indice, persona in enumerate(ordenadas)]

        # Reparto uniforme sobre el 90% del periodo, dejando margen final para
        # los reintentos de los que hayan fallado.
        total = len(ordenadas)
        duracion = (periodo.fin - periodo.inicio).total_seconds()
        return [
            (
                persona.id,
                indice,
                periodo.inicio + timedelta(seconds=duracion * indice / total * 0.9),
            )
            for indice, persona in enumerate(ordenadas)
        ]

    def _instantanea_configuracion(
        self, dias: int, *, distribuir: bool = False
    ) -> dict[str, object]:
        cfg = self._politica.configuracion
        return {
            "periodo_dias": dias,
            "max_consultas_por_hora": cfg.max_consultas_por_hora,
            "franja_pico": f"{cfg.hora_inicio_pico:02d}:00-{cfg.hora_fin_pico:02d}:00",
            "franja_valle": f"{cfg.hora_fin_pico:02d}:00-{cfg.hora_fin_valle:02d}:00",
            "peso_pico": cfg.peso_pico,
            "peso_valle": cfg.peso_valle,
            "demora_segundos": [cfg.demora_minima_segundos, cfg.demora_maxima_segundos],
            "umbral_cortacircuitos": cfg.umbral_cortacircuitos,
            "distribuido_en_periodo": distribuir,
        }


class AvanzarJob(CasoDeUso[UUID, PasoJob]):
    """Ejecuta un paso del job: decide, consulta si toca, y dice cuanto esperar.

    Se invoca en bucle desde el planificador. Cada llamada es autonoma y
    transaccional: si el proceso muere entre dos llamadas, el estado en la base
    ya refleja todo lo hecho y la siguiente ejecucion retoma exactamente donde
    quedo. Esa es la propiedad que permite que un job dure dias.
    """

    nombre = "consultas.avanzar_job"
    descripcion = "Ejecuta un paso del job de cobertura"
    permiso_requerido = Permiso.CONSULTAS_EJECUTAR

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        proveedor: ProveedorConsultaTitulos,
        reconciliador: ReconciliadorTitulos,
        politica: PoliticaPlanificacion,
        reloj: Reloj,
    ) -> None:
        self._uow = uow
        self._proveedor = proveedor
        self._reconciliador = reconciliador
        self._politica = politica
        self._reloj = reloj

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> PasoJob:
        ahora = self._reloj.ahora()
        ahora_local = self._reloj.ahora_local()

        async with self._uow:
            job = await self._uow.jobs.obtener(entrada)
            if job is None:
                raise NoEncontrado("Job", entrada)

            if not job.estado.admite_procesamiento:
                return PasoJob(
                    job_id=job.id,
                    hubo_consulta=False,
                    esperar_segundos=300,
                    motivo=f"El job esta en estado {job.estado.value}",
                    job_pausado=job.estado is EstadoJob.PAUSADO,
                )

            # ¿Terminamos?
            if await self._uow.jobs.contar_items_pendientes(job.id) == 0:
                if job.esperando_desafio > 0:
                    return PasoJob(
                        job_id=job.id,
                        hubo_consulta=False,
                        esperar_segundos=120,
                        motivo=(
                            f"{job.esperando_desafio} consulta(s) esperando resolucion "
                            "manual del desafio de verificacion"
                        ),
                    )
                job.completar(ahora)
                await self._uow.jobs.actualizar(job)
                await self._uow.commit()
                return PasoJob(
                    job_id=job.id,
                    hubo_consulta=False,
                    esperar_segundos=0,
                    motivo="Cobertura completa del periodo",
                    job_completado=True,
                )

            # ¿Toca consultar ahora, segun la politica de ritmo?
            consultas_hora = await self._uow.logs.contar_en_ventana(
                ahora - timedelta(hours=1), ahora
            )
            decision = self._politica.decidir(
                momento_local=ahora_local,
                consultas_en_la_hora=consultas_hora,
                fallos_consecutivos=job.fallos_consecutivos,
            )
            if not decision.puede_consultar:
                return self._sin_consulta(job, decision)

            item = await self._uow.jobs.siguiente_item(job.id, ahora=ahora)
            if item is None:
                return PasoJob(
                    job_id=job.id,
                    hubo_consulta=False,
                    esperar_segundos=180,
                    motivo="No hay items listos: los pendientes estan programados a futuro",
                )

            paso = await self._procesar_item(job, item, decision, contexto)
            await self._uow.commit()
            return paso

    def _sin_consulta(self, job: JobCobertura, decision: DecisionRitmo) -> PasoJob:
        return PasoJob(
            job_id=job.id,
            hubo_consulta=False,
            esperar_segundos=decision.esperar_segundos,
            motivo=decision.motivo,
        )

    async def _procesar_item(
        self,
        job: JobCobertura,
        item: ItemJob,
        decision: DecisionRitmo,
        contexto: ContextoEjecucion,
    ) -> PasoJob:
        persona = await self._uow.personas.obtener(item.persona_id)

        if persona is None or not persona.activo:
            item.omitir("La persona fue eliminada o esta inactiva")
            job.omitidos += 1
            await self._uow.jobs.actualizar_item(item)
            await self._uow.jobs.actualizar(job)
            return PasoJob(
                job_id=job.id,
                hubo_consulta=False,
                esperar_segundos=0,
                motivo="Item omitido: persona inactiva o inexistente",
            )

        item.tomar()
        await self._uow.jobs.actualizar_item(item)

        ejecutor = EjecutorConsulta(self._uow, self._proveedor, self._reconciliador, self._reloj)
        resultado = await ejecutor.ejecutar(
            persona, job_id=job.id, intento=item.intentos, ejecutado_por=contexto.actor_id
        )

        cfg = self._politica.configuracion
        estado = resultado.log.estado

        if estado is EstadoConsulta.DESAFIO_PENDIENTE and resultado.desafio_id:
            item.esperar_desafio(resultado.desafio_id, resultado.log.id)
        elif estado.es_error:
            item.fallar(
                resultado.log.id,
                resultado.log.mensaje or "Error sin detalle",
                reintentable=estado is not EstadoConsulta.ERROR_DATOS,
                max_intentos=cfg.max_intentos_por_persona,
            )
            if item.estado is EstadoItemJob.PENDIENTE:
                item.programado_para = self._reloj.ahora() + self._politica.retroceso(item.intentos)
        else:
            item.completar(resultado.log.id, self._reloj.ahora())

        job.registrar_resultado(estado, umbral_cortacircuitos=cfg.umbral_cortacircuitos)

        await self._uow.jobs.actualizar_item(item)
        await self._uow.jobs.actualizar(job)

        return PasoJob(
            job_id=job.id,
            hubo_consulta=True,
            esperar_segundos=decision.esperar_segundos,
            motivo=decision.motivo,
            resultado=resultado,
            job_pausado=job.estado is EstadoJob.PAUSADO,
        )


class ControlarJob(CasoDeUso[EntradaControlJob, JobCobertura]):
    """Inicia, pausa, reanuda o cancela una campana."""

    nombre = "consultas.controlar_job"
    descripcion = "Inicia, pausa, reanuda o cancela un job de cobertura"
    permiso_requerido = Permiso.CONSULTAS_ADMINISTRAR

    _ACCIONES = frozenset({"iniciar", "pausar", "reanudar", "cancelar"})

    def __init__(self, uow: UnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = uow
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaControlJob, contexto: ContextoEjecucion
    ) -> JobCobertura:
        accion = entrada.accion.strip().lower()
        if accion not in self._ACCIONES:
            raise ReglaDeNegocioViolada(
                f"Accion desconocida: '{entrada.accion}'. "
                f"Validas: {', '.join(sorted(self._ACCIONES))}"
            )

        async with self._uow:
            job = await self._uow.jobs.obtener(entrada.job_id)
            if job is None:
                raise NoEncontrado("Job", entrada.job_id)

            match accion:
                case "iniciar":
                    job.iniciar(self._reloj.ahora())
                case "pausar":
                    job.pausar(entrada.motivo or "Pausado por un operador")
                case "reanudar":
                    job.reanudar()
                case "cancelar":
                    job.cancelar(entrada.motivo or "Cancelado por un operador")

            actualizado = await self._uow.jobs.actualizar(job)
            await self._uow.commit()
            return actualizado


# ---------------------------------------------------------------------------
# Desafios de verificacion humana
# ---------------------------------------------------------------------------


class ResolverDesafio(CasoDeUso[EntradaResolverDesafio, ResultadoEjecucion]):
    """Recibe la respuesta del operador y reanuda la consulta en espera.

    Este es el camino que el sistema toma cuando el proveedor exige una
    verificacion humana. No hay resolucion automatizada: una persona lee el
    desafio en la interfaz y transcribe la respuesta. Fue una decision explicita
    del diseno, registrada en `docs/adr/0005-consultas-senescyt.md`.
    """

    nombre = "consultas.resolver_desafio"
    descripcion = "Aporta la respuesta humana a un desafio de verificacion"
    permiso_requerido = Permiso.CONSULTAS_RESOLVER

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        proveedor: ProveedorConsultaTitulos,
        reconciliador: ReconciliadorTitulos,
        reloj: Reloj,
    ) -> None:
        self._uow = uow
        self._proveedor = proveedor
        self._reconciliador = reconciliador
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaResolverDesafio, contexto: ContextoEjecucion
    ) -> ResultadoEjecucion:
        if not entrada.respuesta.strip():
            raise ReglaDeNegocioViolada("La respuesta al desafio no puede estar vacia")

        async with self._uow:
            item = await self._uow.jobs.obtener_item_por_desafio(entrada.desafio_id)
            if item is None:
                raise NoEncontrado("Desafio", entrada.desafio_id)
            if item.estado is not EstadoItemJob.ESPERANDO_DESAFIO:
                raise ConflictoDeEstado(f"El desafio ya fue atendido (estado: {item.estado.value})")

            persona = await self._uow.personas.obtener(item.persona_id)
            if persona is None:
                item.omitir("La persona fue eliminada mientras el desafio estaba pendiente")
                await self._uow.jobs.actualizar_item(item)
                await self._uow.commit()
                raise NoEncontrado("Persona", item.persona_id)

            log_previo = (
                await self._uow.logs.obtener(item.ultimo_log_id) if item.ultimo_log_id else None
            )
            contexto_desafio = (log_previo.respuesta_cruda or {}) if log_previo else {}

            ejecutor = EjecutorConsulta(
                self._uow, self._proveedor, self._reconciliador, self._reloj
            )
            resultado = await ejecutor.reanudar_con_respuesta(
                persona,
                desafio_id=entrada.desafio_id,
                respuesta_operador=entrada.respuesta.strip(),
                contexto_desafio=contexto_desafio,
                job_id=item.job_id,
                ejecutado_por=contexto.actor_id,
            )

            estado = resultado.log.estado
            if estado is EstadoConsulta.DESAFIO_PENDIENTE and resultado.desafio_id:
                # La respuesta fue incorrecta: el proveedor emite otro desafio.
                item.esperar_desafio(resultado.desafio_id, resultado.log.id)
            elif estado.es_error:
                item.fallar(
                    resultado.log.id,
                    resultado.log.mensaje or "Error tras resolver el desafio",
                    reintentable=True,
                    max_intentos=3,
                )
            else:
                item.completar(resultado.log.id, self._reloj.ahora())

            job = await self._uow.jobs.obtener(item.job_id)
            if job is not None and estado is not EstadoConsulta.DESAFIO_PENDIENTE:
                job.registrar_desafio_resuelto()
                job.registrar_resultado(estado, umbral_cortacircuitos=5)
                await self._uow.jobs.actualizar(job)

            await self._uow.jobs.actualizar_item(item)
            await self._uow.commit()
            return resultado


# ---------------------------------------------------------------------------
# Consultas de lectura
# ---------------------------------------------------------------------------


class ListarLogsConsulta(CasoDeUso[EntradaListarLogs, Pagina[ConsultaLog]]):
    """Historico de consultas: la bitacora de todo lo intentado."""

    nombre = "consultas.listar_logs"
    descripcion = "Consulta el historico de consultas al registro nacional"
    permiso_requerido = Permiso.CONSULTAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarLogs, contexto: ContextoEjecucion
    ) -> Pagina[ConsultaLog]:
        async with self._uow:
            return await self._uow.logs.listar(entrada.filtro, entrada.paginacion)


class ListarJobs(CasoDeUso[Paginacion, Pagina[JobCobertura]]):
    nombre = "consultas.listar_jobs"
    descripcion = "Lista las campanas de actualizacion"
    permiso_requerido = Permiso.CONSULTAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: Paginacion, contexto: ContextoEjecucion
    ) -> Pagina[JobCobertura]:
        async with self._uow:
            return await self._uow.jobs.listar(entrada)


class ObtenerJob(CasoDeUso[UUID, JobCobertura]):
    nombre = "consultas.obtener_job"
    descripcion = "Detalle y progreso de una campana"
    permiso_requerido = Permiso.CONSULTAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> JobCobertura:
        async with self._uow:
            job = await self._uow.jobs.obtener(entrada)
            if job is None:
                raise NoEncontrado("Job", entrada)
            return job
