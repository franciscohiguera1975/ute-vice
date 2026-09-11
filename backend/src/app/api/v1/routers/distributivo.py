"""Endpoints del distributivo docente."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencias import ContenedorDep, ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.distributivo import (
    ColumnaReporteSalida,
    DocenteActualizar,
    DocenteCrear,
    DocenteDetalleSalida,
    DocenteSalida,
    ElementoCatalogoSalida,
    FilaDistributivoActualizar,
    FilaDistributivoCrear,
    FilaDistributivoSalida,
    OpcionSelector,
    PeticionCapturaAsignaturas,
    PeticionReporteDistributivo,
    PlantillaReporteSalida,
    ResultadoCapturaAsignaturasSalida,
    ResumenDistributivoSalida,
    VistaPreviaReporteSalida,
)
from app.application.casos_uso.distributivo import (
    ActualizarFilaDistributivo,
    AsignaturaDeFila,
    CapturarAsignaturas,
    CrearFilaDistributivo,
    EliminarFilaDistributivo,
    EntradaActualizarFila,
    EntradaCrearFila,
    EntradaListarDistributivo,
    ListarDistributivo,
    ObtenerFilaDistributivo,
    ResumenDelDistributivo,
)
from app.application.casos_uso.docentes import (
    ActualizarDocente,
    CrearDocente,
    EliminarDocente,
    EntradaActualizarDocente,
    EntradaCrearDocente,
    EntradaListarDocentes,
    ListarDocentes,
    ObtenerDocente,
)
from app.application.casos_uso.reporte_distributivo import (
    CarrerasDisponibles,
    EntradaCarrerasDisponibles,
    EntradaReporteDistributivo,
    GenerarReporteDistributivo,
    ListarPlantillasReporte,
    VistaPreviaReporteDistributivo,
)
from app.domain.enums import FormatoReporte, Permiso
from app.domain.ports.distributivo import FiltroDistributivo, FiltroDocentes

router = APIRouter(tags=["Distributivo docente"])


# ===========================================================================
# Docentes
# ===========================================================================


@router.get(
    "/docentes",
    response_model=RespuestaPaginada[DocenteSalida],
    summary="Listar docentes",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def listar_docentes(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[str | None, Query(description="Busqueda por nombre o identificacion")] = None,
    genero_id: UUID | None = None,
    activo: bool | None = None,
    solo_con_pasaporte: Annotated[
        bool | None,
        Query(description="Aisla a los docentes sin cedula contrastable"),
    ] = None,
) -> RespuestaPaginada[DocenteSalida]:
    caso = ListarDocentes(uow)
    pagina = await caso(
        EntradaListarDocentes(
            filtro=FiltroDocentes(
                texto=texto,
                genero_id=genero_id,
                activo=activo,
                solo_con_pasaporte=solo_con_pasaporte,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [DocenteSalida.desde(d) for d in pagina.items])


@router.post(
    "/docentes",
    response_model=DocenteSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un docente",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ESCRIBIR)],
    responses={409: {"description": "Ya existe un docente con esa identificacion"}},
)
async def crear_docente(datos: DocenteCrear, uow: UowDep, contexto: ContextoDep) -> DocenteSalida:
    """Acepta cedula o pasaporte: el padron docente incluye extranjeros.

    Si la identificacion es una cedula ya registrada en el modulo de personas,
    se enlaza automaticamente con ese expediente academico.
    """
    caso = CrearDocente(uow)
    docente = await caso(
        EntradaCrearDocente(
            identificacion=datos.identificacion,
            nombre_completo=datos.nombre_completo,
            genero_id=datos.genero_id,
            titulos_ids=tuple(datos.titulos_ids),
            observaciones=datos.observaciones,
        ),
        contexto,
    )
    return DocenteSalida.desde(docente)


@router.get(
    "/docentes/{docente_id}",
    response_model=DocenteDetalleSalida,
    summary="Detalle de un docente",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def obtener_docente(
    docente_id: UUID, uow: UowDep, contexto: ContextoDep
) -> DocenteDetalleSalida:
    caso = ObtenerDocente(uow)
    detalle = await caso(docente_id, contexto)
    return DocenteDetalleSalida(
        docente=DocenteSalida.desde(detalle.docente),
        titulos=[ElementoCatalogoSalida.desde(t) for t in detalle.titulos],
        total_filas=detalle.total_filas,
    )


@router.patch(
    "/docentes/{docente_id}",
    response_model=DocenteSalida,
    summary="Modificar un docente",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ESCRIBIR)],
)
async def actualizar_docente(
    docente_id: UUID, datos: DocenteActualizar, uow: UowDep, contexto: ContextoDep
) -> DocenteSalida:
    """La identificacion no se modifica: es la identidad del docente en el
    consolidado y en todo su historico."""
    caso = ActualizarDocente(uow)
    docente = await caso(
        EntradaActualizarDocente(
            docente_id=docente_id,
            nombre_completo=datos.nombre_completo,
            genero_id=datos.genero_id,
            titulos_ids=tuple(datos.titulos_ids) if datos.titulos_ids is not None else None,
            activo=datos.activo,
            observaciones=datos.observaciones,
        ),
        contexto,
    )
    return DocenteSalida.desde(docente)


@router.delete(
    "/docentes/{docente_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar un docente sin filas",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ELIMINAR)],
    responses={422: {"description": "El docente tiene filas: desactivelo"}},
)
async def eliminar_docente(
    docente_id: UUID, uow: UowDep, contexto: ContextoDep
) -> RespuestaMensaje:
    caso = EliminarDocente(uow)
    await caso(docente_id, contexto)
    return RespuestaMensaje(mensaje="Docente eliminado")


# ===========================================================================
# Filas del distributivo
# ===========================================================================


def _filtro(
    texto: str | None = None,
    docente_id: UUID | None = None,
    pao_id: UUID | None = None,
    facultad_id: UUID | None = None,
    carrera_id: UUID | None = None,
    carrera_ids: list[UUID] | None = None,
    sede_id: UUID | None = None,
    nivel_id: UUID | None = None,
    titularidad_id: UUID | None = None,
    dedicacion_id: UUID | None = None,
    categoria_id: UUID | None = None,
    tipo_titulo_id: UUID | None = None,
    sin_asignatura: bool | None = None,
    con_carga: bool | None = None,
) -> FiltroDistributivo:
    return FiltroDistributivo(
        texto=texto,
        docente_id=docente_id,
        pao_id=pao_id,
        facultad_id=facultad_id,
        carrera_id=carrera_id,
        carrera_ids=tuple(carrera_ids or ()),
        sede_id=sede_id,
        nivel_id=nivel_id,
        titularidad_id=titularidad_id,
        dedicacion_id=dedicacion_id,
        categoria_id=categoria_id,
        tipo_titulo_id=tipo_titulo_id,
        sin_asignatura=sin_asignatura,
        con_carga=con_carga,
    )


FiltroDep = Annotated[FiltroDistributivo, Depends(_filtro)]


@router.get(
    "/distributivo",
    response_model=RespuestaPaginada[FilaDistributivoSalida],
    summary="Listar filas del distributivo",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def listar(
    uow: UowDep,
    contexto: ContextoDep,
    filtro: FiltroDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
) -> RespuestaPaginada[FilaDistributivoSalida]:
    """Admite varias carreras a la vez repitiendo `carrera_ids`."""
    caso = ListarDistributivo(uow)
    pagina = await caso(
        EntradaListarDistributivo(filtro=filtro, paginacion=paginacion.a_dominio()),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [FilaDistributivoSalida.desde(f) for f in pagina.items])


@router.get(
    "/distributivo/resumen",
    response_model=ResumenDistributivoSalida,
    summary="Totales del conjunto filtrado",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def resumen(
    uow: UowDep, contexto: ContextoDep, filtro: FiltroDep
) -> ResumenDistributivoSalida:
    caso = ResumenDelDistributivo(uow)
    return ResumenDistributivoSalida.desde(await caso(filtro, contexto))


@router.post(
    "/distributivo",
    response_model=FilaDistributivoSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una carga docente",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ESCRIBIR)],
    responses={
        409: {"description": "Ya existe una fila para ese docente, periodo, carrera y sede"}
    },
)
async def crear(
    datos: FilaDistributivoCrear, uow: UowDep, contexto: ContextoDep
) -> FilaDistributivoSalida:
    caso = CrearFilaDistributivo(uow)
    fila = await caso(
        EntradaCrearFila(
            docente_id=datos.docente_id,
            pao_id=datos.pao_id,
            facultad_id=datos.facultad_id,
            carrera_id=datos.carrera_id,
            sede_id=datos.sede_id,
            nivel_id=datos.nivel_id,
            titularidad_id=datos.titularidad_id,
            dedicacion_id=datos.dedicacion_id,
            categoria_id=datos.categoria_id,
            tipo_titulo_id=datos.tipo_titulo_id,
            asignatura_id=datos.asignatura_id,
            horas=datos.horas,
            medida=datos.medida,
            observaciones=datos.observaciones,
        ),
        contexto,
    )
    resuelta = await ObtenerFilaDistributivo(uow)(fila.id, contexto)
    return FilaDistributivoSalida.desde(resuelta)


@router.patch(
    "/distributivo/asignaturas",
    response_model=ResultadoCapturaAsignaturasSalida,
    summary="Registrar la asignatura que imparte en varias filas",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ESCRIBIR)],
)
async def capturar_asignaturas(
    datos: PeticionCapturaAsignaturas,
    uow: UowDep,
    contexto: ContextoDep,
) -> ResultadoCapturaAsignaturasSalida:
    """Guarda una tanda de asignaturas.

    La asignatura no viene del consolidado y hay que capturarla a mano para
    cientos de filas; una peticion por fila haria la tarea impracticable. La
    tanda entera va en una transaccion.
    """
    caso = CapturarAsignaturas(uow)
    resultado = await caso(
        [AsignaturaDeFila(fila_id=f.fila_id, asignatura=f.asignatura) for f in datos.filas],
        contexto,
    )
    return ResultadoCapturaAsignaturasSalida(
        actualizadas=resultado.actualizadas,
        sin_cambios=resultado.sin_cambios,
        asignaturas_creadas=resultado.asignaturas_creadas,
    )


@router.get(
    "/distributivo/{fila_id}",
    response_model=FilaDistributivoSalida,
    summary="Obtener una fila",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def obtener(fila_id: UUID, uow: UowDep, contexto: ContextoDep) -> FilaDistributivoSalida:
    caso = ObtenerFilaDistributivo(uow)
    return FilaDistributivoSalida.desde(await caso(fila_id, contexto))


@router.patch(
    "/distributivo/{fila_id}",
    response_model=FilaDistributivoSalida,
    summary="Modificar una fila",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ESCRIBIR)],
)
async def actualizar(
    fila_id: UUID, datos: FilaDistributivoActualizar, uow: UowDep, contexto: ContextoDep
) -> FilaDistributivoSalida:
    """El docente y el periodo no se modifican: junto con la carrera y la sede
    son la identidad de la fila."""
    caso = ActualizarFilaDistributivo(uow)
    await caso(
        EntradaActualizarFila(
            fila_id=fila_id,
            facultad_id=datos.facultad_id,
            carrera_id=datos.carrera_id,
            sede_id=datos.sede_id,
            nivel_id=datos.nivel_id,
            titularidad_id=datos.titularidad_id,
            dedicacion_id=datos.dedicacion_id,
            categoria_id=datos.categoria_id,
            tipo_titulo_id=datos.tipo_titulo_id,
            asignatura_id=datos.asignatura_id,
            horas=datos.horas,
            medida=datos.medida,
            observaciones=datos.observaciones,
        ),
        contexto,
    )
    return FilaDistributivoSalida.desde(await ObtenerFilaDistributivo(uow)(fila_id, contexto))


@router.delete(
    "/distributivo/{fila_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar una fila",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_ELIMINAR)],
)
async def eliminar(fila_id: UUID, uow: UowDep, contexto: ContextoDep) -> RespuestaMensaje:
    caso = EliminarFilaDistributivo(uow)
    await caso(fila_id, contexto)
    return RespuestaMensaje(mensaje="Fila eliminada")


# ===========================================================================
# Exportacion
# ===========================================================================


@router.get(
    "/reportes/distributivo/plantillas",
    response_model=list[PlantillaReporteSalida],
    summary="Plantillas de exportacion disponibles",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
)
async def listar_plantillas(contexto: ContextoDep) -> list[PlantillaReporteSalida]:
    """Que formatos de exportacion hay.

    La interfaz los pide en lugar de tenerlos fijos: sumar una plantilla nueva
    en el backend la hace aparecer sola en el selector.
    """
    plantillas = await ListarPlantillasReporte()(None, contexto)
    return [
        PlantillaReporteSalida(
            codigo=p.codigo,
            nombre=p.nombre,
            descripcion=p.descripcion,
            admite_auditoria=p.admite_auditoria,
        )
        for p in plantillas
    ]


@router.get(
    "/reportes/distributivo/carreras",
    response_model=list[OpcionSelector],
    summary="Carreras presentes en los periodos y facultades indicados",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def carreras_disponibles(
    uow: UowDep,
    contexto: ContextoDep,
    pao_ids: Annotated[list[UUID] | None, Query(description="Periodos academicos")] = None,
    facultad_ids: Annotated[list[UUID] | None, Query(description="Facultades")] = None,
) -> list[OpcionSelector]:
    """La relacion entre facultades y carreras, tal como esta en los datos.

    No sale de una columna del catalogo: doce carreras se dictan en dos
    facultades a la vez, y una columna obligaria a elegir una y a equivocarse
    en la otra.
    """
    caso = CarrerasDisponibles(uow)
    carreras = await caso(
        EntradaCarrerasDisponibles(
            pao_ids=tuple(pao_ids or ()),
            facultad_ids=tuple(facultad_ids or ()),
        ),
        contexto,
    )
    return [OpcionSelector.desde(c) for c in carreras]


@router.post(
    "/reportes/distributivo/vista-previa",
    response_model=VistaPreviaReporteSalida,
    summary="Previsualizar una exportacion del distributivo",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
)
async def vista_previa_reporte(
    datos: PeticionReporteDistributivo,
    uow: UowDep,
    contexto: ContextoDep,
    contenedor: ContenedorDep,
) -> VistaPreviaReporteSalida:
    """Muestra que saldria antes de descargarlo.

    Informa cuantas filas irian sin asignatura, que es el dato que hay que
    completar antes de enviar el archivo.
    """
    caso = VistaPreviaReporteDistributivo(uow, contenedor.reloj)
    vista = await caso(
        EntradaReporteDistributivo(
            pao_ids=tuple(datos.pao_ids),
            facultad_ids=tuple(datos.facultad_ids),
            carrera_ids=tuple(datos.carrera_ids),
            plantilla=datos.plantilla,
            incluir_columnas_auditoria=datos.incluir_columnas_auditoria,
        ),
        contexto,
    )
    return VistaPreviaReporteSalida(
        plantilla=vista.plantilla,
        nombre_plantilla=vista.nombre_plantilla,
        columnas=[ColumnaReporteSalida.desde(c) for c in vista.columnas],
        filas=[[fila.get(c.clave) for c in vista.columnas] for fila in vista.filas],
        total_filas=vista.total_filas,
        total_docentes=vista.total_docentes,
        sin_asignatura=vista.sin_asignatura,
        sin_anio_inicio=vista.sin_anio_inicio,
        periodos=vista.periodos,
        facultades=vista.facultades,
        carreras=vista.carreras,
        esta_completo=vista.esta_completo,
    )


@router.post(
    "/reportes/distributivo",
    summary="Exportar el distributivo con una plantilla",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
    responses={
        200: {"description": "Archivo generado"},
        422: {"description": "Ningun docente cumple los filtros"},
    },
)
async def generar_reporte(
    datos: PeticionReporteDistributivo,
    uow: UowDep,
    contexto: ContextoDep,
    contenedor: ContenedorDep,
    formato: FormatoReporte = FormatoReporte.XLSX,
) -> Response:
    """Genera el archivo con la plantilla elegida.

    Se puede acotar por facultad y por varias carreras a la vez.
    """
    caso = GenerarReporteDistributivo(
        uow,
        contenedor.exportadores,
        contenedor.reloj,
        max_filas=contenedor.settings.reports.max_rows,
    )
    archivo = await caso(
        EntradaReporteDistributivo(
            pao_ids=tuple(datos.pao_ids),
            facultad_ids=tuple(datos.facultad_ids),
            carrera_ids=tuple(datos.carrera_ids),
            plantilla=datos.plantilla,
            formato=formato,
            incluir_columnas_auditoria=datos.incluir_columnas_auditoria,
        ),
        contexto,
    )
    nombre = archivo.nombre_archivo
    return Response(
        content=archivo.contenido,
        media_type=archivo.tipo_mime,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{nombre}\"; filename*=UTF-8''{quote(nombre)}"
            ),
            "Content-Length": str(archivo.tamano_bytes),
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Length",
        },
    )
