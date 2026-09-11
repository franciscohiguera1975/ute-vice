"""Endpoints de personas (empleados)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.nucleo import (
    ErrorImportacionSalida,
    FilaImportacionEntrada,
    PersonaActualizar,
    PersonaCrear,
    PersonaDetalleSalida,
    PersonaSalida,
    ResultadoImportacionSalida,
)
from app.application.casos_uso.personas import (
    ActualizarPersona,
    CrearPersona,
    EliminarPersona,
    EntradaActualizarPersona,
    EntradaCrearPersona,
    EntradaListarPersonas,
    FilaImportacion,
    ImportarPersonas,
    ListarPersonas,
    ObtenerPersona,
    ObtenerPersonaPorCedula,
)
from app.domain.enums import EstadoConsulta, Permiso, TipoVinculacion
from app.domain.ports.repositorios import FiltroPersonas

router = APIRouter(prefix="/personas", tags=["Personas"])


@router.get(
    "",
    response_model=RespuestaPaginada[PersonaSalida],
    summary="Listar personas",
    dependencies=[requiere(Permiso.PERSONAS_LEER)],
)
async def listar(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[
        str | None, Query(description="Busqueda por nombre, cedula, unidad o codigo")
    ] = None,
    unidad: str | None = None,
    tipo_vinculacion: TipoVinculacion | None = None,
    activo: bool | None = None,
    con_titulos: Annotated[
        bool | None,
        Query(description="false aisla a las personas sin ningun titulo registrado"),
    ] = None,
    nunca_consultadas: Annotated[
        bool | None, Query(description="true devuelve solo las que jamas se han consultado")
    ] = None,
    estado_ultima_consulta: EstadoConsulta | None = None,
) -> RespuestaPaginada[PersonaSalida]:
    caso = ListarPersonas(uow)
    pagina = await caso(
        EntradaListarPersonas(
            filtro=FiltroPersonas(
                texto=texto,
                unidad=unidad,
                tipo_vinculacion=tipo_vinculacion,
                activo=activo,
                con_titulos=con_titulos,
                nunca_consultadas=nunca_consultadas,
                estado_ultima_consulta=estado_ultima_consulta,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [PersonaSalida.desde(p) for p in pagina.items])


@router.post(
    "",
    response_model=PersonaSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una persona",
    dependencies=[requiere(Permiso.PERSONAS_ESCRIBIR)],
    responses={409: {"description": "Ya existe una persona con esa cedula"}},
)
async def crear(datos: PersonaCrear, uow: UowDep, contexto: ContextoDep) -> PersonaSalida:
    caso = CrearPersona(uow)
    persona = await caso(
        EntradaCrearPersona(
            cedula=datos.cedula,
            nombres=datos.nombres,
            apellidos=datos.apellidos,
            email_institucional=datos.email_institucional,
            email_personal=datos.email_personal,
            telefono=datos.telefono,
            tipo_vinculacion=datos.tipo_vinculacion,
            unidad=datos.unidad,
            cargo=datos.cargo,
            codigo_empleado=datos.codigo_empleado,
            fecha_ingreso=datos.fecha_ingreso,
            fecha_nacimiento=datos.fecha_nacimiento,
            observaciones=datos.observaciones,
        ),
        contexto,
    )
    return PersonaSalida.desde(persona)


@router.get(
    "/cedula/{cedula}",
    response_model=PersonaDetalleSalida,
    summary="Buscar una persona por cedula",
    dependencies=[requiere(Permiso.PERSONAS_LEER)],
)
async def obtener_por_cedula(
    cedula: str, uow: UowDep, contexto: ContextoDep
) -> PersonaDetalleSalida:
    caso = ObtenerPersonaPorCedula(uow)
    return PersonaDetalleSalida.desde(await caso(cedula, contexto))


@router.get(
    "/{persona_id}",
    response_model=PersonaDetalleSalida,
    summary="Detalle de una persona con su expediente academico",
    dependencies=[requiere(Permiso.PERSONAS_LEER)],
)
async def obtener(persona_id: UUID, uow: UowDep, contexto: ContextoDep) -> PersonaDetalleSalida:
    caso = ObtenerPersona(uow)
    return PersonaDetalleSalida.desde(await caso(persona_id, contexto))


@router.patch(
    "/{persona_id}",
    response_model=PersonaSalida,
    summary="Actualizar una persona",
    dependencies=[requiere(Permiso.PERSONAS_ESCRIBIR)],
)
async def actualizar(
    persona_id: UUID, datos: PersonaActualizar, uow: UowDep, contexto: ContextoDep
) -> PersonaSalida:
    """La cedula no es modificable: identifica a la persona ante el registro
    nacional y cambiarla invalidaria todo su historico."""
    caso = ActualizarPersona(uow)
    persona = await caso(
        EntradaActualizarPersona(
            persona_id=persona_id,
            nombres=datos.nombres,
            apellidos=datos.apellidos,
            email_institucional=datos.email_institucional,
            email_personal=datos.email_personal,
            telefono=datos.telefono,
            tipo_vinculacion=datos.tipo_vinculacion,
            unidad=datos.unidad,
            cargo=datos.cargo,
            codigo_empleado=datos.codigo_empleado,
            fecha_ingreso=datos.fecha_ingreso,
            fecha_nacimiento=datos.fecha_nacimiento,
            observaciones=datos.observaciones,
            activo=datos.activo,
        ),
        contexto,
    )
    return PersonaSalida.desde(persona)


@router.delete(
    "/{persona_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar una persona sin expediente",
    dependencies=[requiere(Permiso.PERSONAS_ELIMINAR)],
    responses={
        422: {
            "description": "La persona tiene titulos o historico: debe desactivarse, no eliminarse"
        }
    },
)
async def eliminar(persona_id: UUID, uow: UowDep, contexto: ContextoDep) -> RespuestaMensaje:
    caso = EliminarPersona(uow)
    await caso(persona_id, contexto)
    return RespuestaMensaje(mensaje="Persona eliminada")


@router.post(
    "/importar",
    response_model=ResultadoImportacionSalida,
    summary="Carga masiva de personas",
    dependencies=[requiere(Permiso.PERSONAS_IMPORTAR)],
)
async def importar(
    filas: list[FilaImportacionEntrada], uow: UowDep, contexto: ContextoDep
) -> ResultadoImportacionSalida:
    """Carga un lote de personas.

    Una fila invalida no aborta el lote: se informa fila a fila para que el
    responsable corrija el archivo de origen.
    """
    caso = ImportarPersonas(uow)
    resultado = await caso(
        [
            FilaImportacion(
                cedula=f.cedula,
                nombres=f.nombres,
                apellidos=f.apellidos,
                email_institucional=f.email_institucional,
                tipo_vinculacion=f.tipo_vinculacion,
                unidad=f.unidad,
                cargo=f.cargo,
                codigo_empleado=f.codigo_empleado,
            )
            for f in filas
        ],
        contexto,
    )
    return ResultadoImportacionSalida(
        total_filas=resultado.total_filas,
        creadas=resultado.creadas,
        duplicadas=resultado.duplicadas,
        rechazadas=[
            ErrorImportacionSalida(fila=e.fila, cedula=e.cedula, motivo=e.motivo)
            for e in resultado.rechazadas
        ],
        exitosa=resultado.exitosa,
    )
