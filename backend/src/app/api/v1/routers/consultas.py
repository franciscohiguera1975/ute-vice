"""Endpoints de consulta al registro nacional de titulos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import (
    ContenedorDep,
    ContextoDep,
    UowDep,
    requiere,
)
from app.api.esquemas.comunes import ParametrosPaginacion, RespuestaPaginada
from app.api.esquemas.nucleo import (
    ConsultaLogSalida,
    ControlJobEntrada,
    JobCreadoSalida,
    JobCrear,
    JobSalida,
    ResolverDesafioEntrada,
    ResultadoConsultaSalida,
)
from app.application.casos_uso.consultas import (
    AvanzarJob,
    ConsultarPersona,
    ControlarJob,
    CrearJobCobertura,
    EntradaConsultarPersona,
    EntradaControlJob,
    EntradaCrearJob,
    EntradaListarLogs,
    EntradaResolverDesafio,
    ListarJobs,
    ListarLogsConsulta,
    ObtenerJob,
    ResolverDesafio,
)
from app.domain.enums import EstadoConsulta, Permiso
from app.domain.ports.repositorios import FiltroLogs

router = APIRouter(prefix="/consultas", tags=["Consultas SENESCYT"])


# ---------------------------------------------------------------------------
# Consulta puntual
# ---------------------------------------------------------------------------


@router.post(
    "/personas/{persona_id}",
    response_model=ResultadoConsultaSalida,
    summary="Consultar los titulos de una persona",
    dependencies=[requiere(Permiso.CONSULTAS_EJECUTAR)],
    responses={
        409: {"description": "La persona ya fue consultada dentro del periodo vigente"},
        202: {"description": "La consulta requiere resolucion humana del desafio"},
    },
)
async def consultar_persona(
    persona_id: UUID,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
    forzar: Annotated[
        bool,
        Query(
            description=(
                "Ignora la regla de cobertura del periodo. Usar solo con "
                "justificacion: erosiona el reparto de carga del planificador."
            )
        ),
    ] = False,
) -> ResultadoConsultaSalida:
    """Lanza una consulta bajo demanda.

    Si el proveedor exige verificacion humana, la respuesta trae
    `requiere_intervencion=true` y un `desafio_id` que se resuelve desde la cola
    de desafios.
    """
    caso = ConsultarPersona(
        uow,
        contenedor.proveedor_titulos,
        contenedor.reconciliador,
        contenedor.reloj,
        contenedor.politica_planificacion,
    )
    resultado = await caso(EntradaConsultarPersona(persona_id=persona_id, forzar=forzar), contexto)
    return ResultadoConsultaSalida.desde(resultado)


# ---------------------------------------------------------------------------
# Historico
# ---------------------------------------------------------------------------


@router.get(
    "/logs",
    response_model=RespuestaPaginada[ConsultaLogSalida],
    summary="Historico de consultas",
    dependencies=[requiere(Permiso.CONSULTAS_LEER)],
)
async def listar_logs(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    persona_id: UUID | None = None,
    job_id: UUID | None = None,
    cedula: str | None = None,
    estado: EstadoConsulta | None = None,
    solo_errores: bool = False,
    solo_con_cambios: Annotated[
        bool, Query(description="true devuelve solo las consultas que detectaron cambios")
    ] = False,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> RespuestaPaginada[ConsultaLogSalida]:
    """Bitacora completa. Toda consulta deja una fila aqui, exitosa o no.

    Es la tabla que responde "por que el dato de esta persona esta desfasado".
    """
    caso = ListarLogsConsulta(uow)
    pagina = await caso(
        EntradaListarLogs(
            filtro=FiltroLogs(
                persona_id=persona_id,
                job_id=job_id,
                cedula=cedula,
                estado=estado,
                solo_errores=solo_errores,
                solo_con_cambios=solo_con_cambios,
                desde=desde,
                hasta=hasta,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [ConsultaLogSalida.desde(log) for log in pagina.items])


# ---------------------------------------------------------------------------
# Jobs de cobertura
# ---------------------------------------------------------------------------


@router.get(
    "/jobs",
    response_model=RespuestaPaginada[JobSalida],
    summary="Listar campanas de actualizacion",
    dependencies=[requiere(Permiso.CONSULTAS_LEER)],
)
async def listar_jobs(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
) -> RespuestaPaginada[JobSalida]:
    caso = ListarJobs(uow)
    pagina = await caso(paginacion.a_dominio(), contexto)
    return RespuestaPaginada.desde(pagina, [JobSalida.desde(j) for j in pagina.items])


@router.post(
    "/jobs",
    response_model=JobCreadoSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una campana de cobertura del padron",
    dependencies=[requiere(Permiso.CONSULTAS_ADMINISTRAR)],
    responses={409: {"description": "Ya existe un job activo"}},
)
async def crear_job(
    datos: JobCrear, contenedor: ContenedorDep, uow: UowDep, contexto: ContextoDep
) -> JobCreadoSalida:
    """Arma la cola de personas a consultar durante el periodo.

    La respuesta incluye una evaluacion de factibilidad: si el periodo no
    alcanza para cubrir a todo el padron con el ritmo configurado, se advierte.
    La respuesta correcta es ampliar el periodo, no acelerar las consultas.
    """
    caso = CrearJobCobertura(
        uow, contenedor.politica_planificacion, contenedor.reloj, contenedor.aleatorio
    )
    resultado = await caso(
        EntradaCrearJob(
            nombre=datos.nombre,
            periodo_dias=datos.periodo_dias,
            limite_personas=datos.limite_personas,
            iniciar_inmediatamente=datos.iniciar_inmediatamente,
            distribuir_en_periodo=datos.distribuir_en_periodo,
        ),
        contexto,
    )
    return JobCreadoSalida(
        job=JobSalida.desde(resultado.job),
        factible=resultado.factibilidad.es_factible,
        consultas_diarias_estimadas=resultado.factibilidad.consultas_diarias_estimadas,
        dias_necesarios=resultado.factibilidad.dias_necesarios,
        advertencia=resultado.advertencia,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobSalida,
    summary="Detalle y progreso de una campana",
    dependencies=[requiere(Permiso.CONSULTAS_LEER)],
)
async def obtener_job(job_id: UUID, uow: UowDep, contexto: ContextoDep) -> JobSalida:
    caso = ObtenerJob(uow)
    return JobSalida.desde(await caso(job_id, contexto))


@router.post(
    "/jobs/{job_id}/control",
    response_model=JobSalida,
    summary="Iniciar, pausar, reanudar o cancelar una campana",
    dependencies=[requiere(Permiso.CONSULTAS_ADMINISTRAR)],
)
async def controlar_job(
    job_id: UUID,
    datos: ControlJobEntrada,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
) -> JobSalida:
    caso = ControlarJob(uow, contenedor.reloj)
    job = await caso(
        EntradaControlJob(job_id=job_id, accion=datos.accion, motivo=datos.motivo),
        contexto,
    )
    return JobSalida.desde(job)


@router.post(
    "/jobs/{job_id}/avanzar",
    response_model=dict[str, Any],
    summary="Ejecutar un paso de la campana",
    dependencies=[requiere(Permiso.CONSULTAS_EJECUTAR)],
)
async def avanzar_job(
    job_id: UUID, contenedor: ContenedorDep, uow: UowDep, contexto: ContextoDep
) -> dict[str, Any]:
    """Avanza el job una consulta.

    Normalmente lo invoca el planificador en segundo plano. Este endpoint existe
    para operar la campana a mano cuando `SCHEDULER_ENABLED=false`, y para
    diagnosticar: la respuesta explica por que se consulto o por que no.
    """
    caso = AvanzarJob(
        uow,
        contenedor.proveedor_titulos,
        contenedor.reconciliador,
        contenedor.politica_planificacion,
        contenedor.reloj,
    )
    paso = await caso(job_id, contexto)
    return {
        "job_id": str(paso.job_id),
        "hubo_consulta": paso.hubo_consulta,
        "esperar_segundos": paso.esperar_segundos,
        "motivo": paso.motivo,
        "job_completado": paso.job_completado,
        "job_pausado": paso.job_pausado,
        "resultado": (
            ResultadoConsultaSalida.desde(paso.resultado).model_dump(mode="json")
            if paso.resultado
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Desafios de verificacion humana
# ---------------------------------------------------------------------------


@router.post(
    "/desafios/resolver",
    response_model=ResultadoConsultaSalida,
    summary="Aportar la respuesta humana a un desafio de verificacion",
    dependencies=[requiere(Permiso.CONSULTAS_RESOLVER)],
    responses={
        404: {"description": "El desafio no existe o expiro"},
        409: {"description": "El desafio ya fue atendido"},
    },
)
async def resolver_desafio(
    datos: ResolverDesafioEntrada,
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
) -> ResultadoConsultaSalida:
    """Reanuda una consulta que quedo esperando verificacion humana.

    El sistema **no resuelve el desafio automaticamente**: una persona lo lee en
    la interfaz y transcribe la respuesta. Ver `docs/SENESCYT.md`.
    """
    caso = ResolverDesafio(
        uow, contenedor.proveedor_titulos, contenedor.reconciliador, contenedor.reloj
    )
    resultado = await caso(
        EntradaResolverDesafio(desafio_id=datos.desafio_id, respuesta=datos.respuesta),
        contexto,
    )
    return ResultadoConsultaSalida.desde(resultado)


@router.get(
    "/estado-planificador",
    response_model=dict[str, Any],
    summary="Estado del planificador y de la politica de ritmo",
    dependencies=[requiere(Permiso.CONSULTAS_LEER)],
)
async def estado_planificador(request_contenedor: ContenedorDep) -> dict[str, Any]:
    """Configuracion vigente y capacidad estimada.

    Util para explicarle a un operador por que el sistema esta esperando en
    lugar de consultar.
    """
    from app.domain.value_objects import ahora_utc

    contenedor = request_contenedor
    politica = contenedor.politica_planificacion
    ahora_local = contenedor.reloj.ahora_local()
    franja = politica.franja_de(ahora_local)

    return {
        "habilitado": contenedor.settings.scheduler.enabled,
        "proveedor": contenedor.proveedor_titulos.nombre,
        "requiere_verificacion_humana": (contenedor.proveedor_titulos.requiere_verificacion_humana),
        "hora_local": ahora_local.isoformat(),
        "franja_actual": franja.value,
        "peso_franja": politica.peso_de(franja),
        "en_horario_operativo": politica.esta_en_horario(ahora_local),
        "proxima_apertura": (
            politica.proxima_apertura(ahora_local).isoformat()
            if not politica.esta_en_horario(ahora_local)
            else None
        ),
        "capacidad_diaria_estimada": politica.consultas_diarias_estimadas(),
        "configuracion": {
            "periodo_dias": politica.configuracion.periodo_dias,
            "max_consultas_por_hora": politica.configuracion.max_consultas_por_hora,
            "franja_pico": (
                f"{politica.configuracion.hora_inicio_pico:02d}:00-"
                f"{politica.configuracion.hora_fin_pico:02d}:00"
            ),
            "franja_valle": (
                f"{politica.configuracion.hora_fin_pico:02d}:00-"
                f"{politica.configuracion.hora_fin_valle:02d}:00"
            ),
            "demora_segundos": [
                politica.configuracion.demora_minima_segundos,
                politica.configuracion.demora_maxima_segundos,
            ],
            "umbral_cortacircuitos": politica.configuracion.umbral_cortacircuitos,
        },
        "consultado_en": ahora_utc().isoformat(),
    }
