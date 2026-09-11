"""Endpoints de generacion de reportes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencias import ContenedorDep, ContextoDep, UowDep, requiere
from app.application.casos_uso.reportes import (
    EntradaReporteConsultas,
    EntradaReportePersonas,
    EntradaReporteTitulos,
    GenerarReporteConsultas,
    GenerarReportePersonas,
    GenerarReporteTitulos,
    ListarFormatosDisponibles,
)
from app.domain.enums import (
    EstadoConsulta,
    EstadoTitulo,
    FormatoReporte,
    NivelTitulo,
    Permiso,
    TipoVinculacion,
)
from app.domain.ports.reportes import ArchivoReporte
from app.domain.ports.repositorios import FiltroLogs, FiltroPersonas, FiltroTitulos

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _descarga(archivo: ArchivoReporte) -> Response:
    """Respuesta binaria con la cabecera de descarga.

    Se usa `filename*` con codificacion UTF-8 ademas de `filename`: sin ello,
    los navegadores estropean los nombres con tildes.
    """
    nombre = archivo.nombre_archivo
    return Response(
        content=archivo.contenido,
        media_type=archivo.tipo_mime,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{nombre}\"; filename*=UTF-8''{quote(nombre)}"
            ),
            "Content-Length": str(archivo.tamano_bytes),
            # El frontend necesita leer estas cabeceras desde otro origen.
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Length",
        },
    )


@router.get(
    "/formatos",
    response_model=list[str],
    summary="Formatos de exportacion disponibles",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
)
async def formatos(contenedor: ContenedorDep, contexto: ContextoDep) -> list[str]:
    caso = ListarFormatosDisponibles(contenedor.exportadores)
    return await caso(None, contexto)


@router.get(
    "/personas",
    summary="Reporte del padron de personas",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "text/csv": {},
                "application/pdf": {},
            },
            "description": "Archivo generado",
        },
        413: {"description": "El reporte excede el maximo de filas permitido"},
    },
)
async def reporte_personas(
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
    formato: FormatoReporte = FormatoReporte.XLSX,
    texto: str | None = None,
    unidad: str | None = None,
    tipo_vinculacion: TipoVinculacion | None = None,
    activo: bool | None = None,
    con_titulos: Annotated[
        bool | None, Query(description="false lista solo a quienes no tienen titulos")
    ] = None,
    nunca_consultadas: bool | None = None,
    incluir_titulos: Annotated[
        bool, Query(description="Genera una fila por titulo en lugar de una por persona")
    ] = False,
) -> Response:
    caso = GenerarReportePersonas(
        uow,
        contenedor.exportadores,
        contenedor.reloj,
        contenedor.settings.reports.max_rows,
    )
    archivo = await caso(
        EntradaReportePersonas(
            formato=formato,
            filtro=FiltroPersonas(
                texto=texto,
                unidad=unidad,
                tipo_vinculacion=tipo_vinculacion,
                activo=activo,
                con_titulos=con_titulos,
                nunca_consultadas=nunca_consultadas,
            ),
            incluir_titulos=incluir_titulos,
        ),
        contexto,
    )
    return _descarga(archivo)


@router.get(
    "/titulos",
    summary="Reporte del inventario de titulos",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
)
async def reporte_titulos(
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
    formato: FormatoReporte = FormatoReporte.XLSX,
    texto: str | None = None,
    persona_id: UUID | None = None,
    nivel: NivelTitulo | None = None,
    estado: EstadoTitulo | None = None,
    institucion: str | None = None,
    verificado: bool | None = None,
    requiere_atencion: bool | None = None,
    registro_desde: date | None = None,
    registro_hasta: date | None = None,
) -> Response:
    caso = GenerarReporteTitulos(
        uow,
        contenedor.exportadores,
        contenedor.reloj,
        contenedor.settings.reports.max_rows,
    )
    archivo = await caso(
        EntradaReporteTitulos(
            formato=formato,
            filtro=FiltroTitulos(
                texto=texto,
                persona_id=persona_id,
                nivel=nivel,
                estado=estado,
                institucion=institucion,
                verificado=verificado,
                requiere_atencion=requiere_atencion,
                registro_desde=registro_desde,
                registro_hasta=registro_hasta,
            ),
        ),
        contexto,
    )
    return _descarga(archivo)


@router.get(
    "/consultas",
    summary="Reporte del historico de consultas",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
)
async def reporte_consultas(
    contenedor: ContenedorDep,
    uow: UowDep,
    contexto: ContextoDep,
    formato: FormatoReporte = FormatoReporte.XLSX,
    persona_id: UUID | None = None,
    job_id: UUID | None = None,
    estado: EstadoConsulta | None = None,
    solo_errores: bool = False,
    solo_con_cambios: bool = False,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> Response:
    """Reporte de auditoria del proceso de validacion."""
    caso = GenerarReporteConsultas(
        uow,
        contenedor.exportadores,
        contenedor.reloj,
        contenedor.settings.reports.max_rows,
    )
    archivo = await caso(
        EntradaReporteConsultas(
            formato=formato,
            filtro=FiltroLogs(
                persona_id=persona_id,
                job_id=job_id,
                estado=estado,
                solo_errores=solo_errores,
                solo_con_cambios=solo_con_cambios,
                desde=desde,
                hasta=hasta,
            ),
        ),
        contexto,
    )
    return _descarga(archivo)
