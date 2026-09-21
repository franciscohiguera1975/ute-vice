"""Endpoints del distributivo docente."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.dependencias import ContenedorDep, ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.distributivo import (
    AmbitoDisponible,
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
    ResultadoImportacionSalida,
    ResumenComparativoSalida,
    ResumenDeHorasSalida,
    ResumenDistributivoSalida,
    TableroDistributivoSalida,
    VistaPreviaReporteSalida,
)
from app.application.casos_uso.analitica import (
    EntradaHorasPorDedicacion,
    EntradaResumenComparativo,
    EntradaTableroDistributivo,
    ObtenerHorasPorDedicacion,
    ObtenerResumenComparativo,
    ObtenerTableroDistributivo,
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
from app.application.casos_uso.importar_distributivo import (
    EntradaImportacion,
    ImportarDistributivo,
)
from app.application.casos_uso.reporte_distributivo import (
    CarrerasDisponibles,
    EntradaCarrerasDisponibles,
    EntradaReporteDistributivo,
    FacultadesDisponibles,
    GenerarReporteDistributivo,
    ListarPlantillasReporte,
    VistaPreviaReporteDistributivo,
)
from app.application.casos_uso.reporte_horas_por_docentes import (
    RESUMEN_BAJO_HORAS,
    RESUMEN_CARRERA,
    RESUMEN_FACULTAD,
    EntradaExportarHoras,
    ExportarHorasPorDocentes,
)
from app.application.casos_uso.reporte_resumenes import (
    RESUMEN_APROBACION,
    RESUMEN_AVANCE,
    RESUMEN_COMPARATIVO,
    RESUMEN_ESTADOS,
    EntradaExportarResumen,
    ExportarResumenDistributivo,
)
from app.domain.enums import FormatoReporte, Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.distributivo import FiltroDistributivo, FiltroDocentes
from app.domain.ports.reportes import ArchivoReporte
from app.infrastructure.importadores.pao_excel import LectorPaoExcel

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
    pao_ids: Annotated[
        list[UUID] | None,
        Query(description="Varios periodos a la vez. Se suma al filtro de uno solo."),
    ] = None,
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
        pao_ids=tuple(pao_ids or ()),
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
            asignaturas_ids=datos.asignaturas_ids,
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


# ===========================================================================
# Tablero del distributivo
# ===========================================================================


@router.get(
    "/distributivo/tablero",
    response_model=TableroDistributivoSalida,
    summary="Avance de la validacion en dos grupos de periodos",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def tablero_distributivo(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    grupo_a: Annotated[
        list[UUID] | None,
        Query(description="Periodos de referencia. Repetir el parametro para varios."),
    ] = None,
    grupo_b: Annotated[list[UUID] | None, Query(description="Periodos que se examinan.")] = None,
) -> TableroDistributivoSalida:
    """Todos los indicadores en una sola llamada.

    Se agrupan igual que en el tablero general: con cinco peticiones
    concurrentes, las cifras de la misma pantalla podrian no cuadrar entre si.

    Sin grupos, se comparan los dos ultimos semestres enteros — la misma
    eleccion que hacen los resumenes, para que las dos pantallas no digan
    cifras distintas del mismo periodo.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica_distributivo(uow.sesion)  # type: ignore[attr-defined]
        caso = ObtenerTableroDistributivo(analitica, contenedor.reloj)
        resultado = await caso(
            EntradaTableroDistributivo(grupo_a=tuple(grupo_a or ()), grupo_b=tuple(grupo_b or ())),
            contexto,
        )
    return TableroDistributivoSalida.desde(resultado)


@router.get(
    "/distributivo/resumenes",
    response_model=ResumenComparativoSalida,
    summary="Comparar dos grupos de periodos",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def resumenes_del_distributivo(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    grupo_a: Annotated[
        list[UUID] | None,
        Query(description="Periodos del primer grupo. Repetir el parametro para varios."),
    ] = None,
    grupo_b: Annotated[list[UUID] | None, Query(description="Periodos del segundo grupo.")] = None,
    dedicacion_ids: Annotated[
        list[UUID] | None,
        Query(description="Filtra por dedicacion. Repetir el parametro para varias."),
    ] = None,
) -> ResumenComparativoSalida:
    """Dos resumenes sobre los mismos grupos: avance y estados por facultad.

    Se piden grupos y no periodos sueltos porque un semestre son varios: el
    `2026-1` completo es tecnologia, grado y posgrado, mas sus interciclos.

    Sin grupos, se comparan los dos ultimos semestres enteros. Sin
    dedicaciones, se incluyen todas.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica_distributivo(uow.sesion)  # type: ignore[attr-defined]
        caso = ObtenerResumenComparativo(analitica, contenedor.reloj)
        resultado = await caso(
            EntradaResumenComparativo(
                grupo_a=tuple(grupo_a or ()),
                grupo_b=tuple(grupo_b or ()),
                dedicacion_ids=tuple(dedicacion_ids or ()),
            ),
            contexto,
        )
    return ResumenComparativoSalida.desde(resultado)


@router.get(
    "/distributivo/horas-por-docentes",
    response_model=ResumenDeHorasSalida,
    summary="Horas de Da por carrera y facultad de un PAO, filtradas por dedicacion",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def horas_por_docentes_del_distributivo(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    grupo: Annotated[
        list[UUID] | None,
        Query(description="Periodos que se examinan. Repetir el parametro para varios."),
    ] = None,
    dedicacion_id: Annotated[
        UUID | None, Query(description="Filtra por dedicacion. Sin ella, se incluyen todas.")
    ] = None,
    menos_de: Annotated[
        float | None,
        Query(description="Ademas, lista los docentes con menos de N horas de Da."),
    ] = None,
) -> ResumenDeHorasSalida:
    """Cuantos docentes hay y cuantas horas de `Da` cargan, por carrera y
    por facultad, acotado a una dedicacion o a todas.

    Se pide un grupo y no periodos sueltos porque un semestre son varios: el
    `2026-1` completo es tecnologia, grado y posgrado, mas sus interciclos.

    Sin grupo, se toma el semestre mas reciente completo.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica_distributivo(uow.sesion)  # type: ignore[attr-defined]
        caso = ObtenerHorasPorDedicacion(analitica, contenedor.reloj)
        resultado = await caso(
            EntradaHorasPorDedicacion(
                grupo=tuple(grupo or ()), dedicacion_id=dedicacion_id, menos_de=menos_de
            ),
            contexto,
        )
    return ResumenDeHorasSalida.desde(resultado)


@router.get(
    "/distributivo/horas-por-docentes/exportar",
    summary="Descargar una tabla de horas por docentes",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
    responses={422: {"description": "No hay datos con los periodos y el filtro elegidos"}},
)
async def exportar_horas_por_docentes(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    resumen: Annotated[
        str,
        Query(description=f"`{RESUMEN_FACULTAD}`, `{RESUMEN_CARRERA}` o `{RESUMEN_BAJO_HORAS}`."),
    ] = RESUMEN_FACULTAD,
    grupo: Annotated[list[UUID] | None, Query(description="Periodos que se examinan.")] = None,
    dedicacion_id: Annotated[
        UUID | None, Query(description="Filtra por dedicacion. Sin ella, se incluyen todas.")
    ] = None,
    menos_de: Annotated[
        float | None,
        Query(description=f"Obligatorio para `{RESUMEN_BAJO_HORAS}`."),
    ] = None,
    formato: FormatoReporte = FormatoReporte.XLSX,
) -> Response:
    """La misma tabla que muestra la pantalla, como archivo.

    Sale del mismo caso de uso de lectura, para que el archivo no pueda decir
    otra cosa que la pantalla.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica_distributivo(uow.sesion)  # type: ignore[attr-defined]
        caso = ExportarHorasPorDocentes(analitica, contenedor.exportadores, contenedor.reloj)
        archivo = await caso(
            EntradaExportarHoras(
                grupo=tuple(grupo or ()),
                dedicacion_id=dedicacion_id,
                menos_de=menos_de,
                resumen=resumen,
                formato=formato,
            ),
            contexto,
        )
    return _como_descarga(archivo)


@router.get(
    "/distributivo/resumenes/exportar",
    summary="Descargar un resumen comparativo",
    dependencies=[requiere(Permiso.REPORTES_GENERAR)],
    response_class=Response,
    responses={
        200: {"description": "Archivo generado"},
        422: {"description": "No hay datos con los periodos elegidos"},
    },
)
async def exportar_resumen(
    contenedor: ContenedorDep,
    contexto: ContextoDep,
    resumen: Annotated[
        str,
        Query(
            description=(
                f"De resumenes: `{RESUMEN_AVANCE}`, `{RESUMEN_ESTADOS}`. "
                f"Del tablero: `{RESUMEN_APROBACION}`, `{RESUMEN_COMPARATIVO}`."
            )
        ),
    ] = RESUMEN_AVANCE,
    grupo_a: Annotated[list[UUID] | None, Query(description="Periodos del primer grupo")] = None,
    grupo_b: Annotated[list[UUID] | None, Query(description="Periodos del segundo grupo")] = None,
    dedicacion_ids: Annotated[
        list[UUID] | None,
        Query(description="Filtra por dedicacion. Solo aplica a `avance` y `estados`."),
    ] = None,
    grupo: Annotated[
        str, Query(description="Para el resumen de estados: que grupo se desglosa, `a` o `b`")
    ] = "b",
    etiqueta_a: Annotated[
        str, Query(description="Como titular el grupo 1. Vacio usa el semestre.", max_length=40)
    ] = "",
    etiqueta_b: Annotated[
        str, Query(description="Como titular el grupo 2. Vacio usa el semestre.", max_length=40)
    ] = "",
    formato: FormatoReporte = FormatoReporte.XLSX,
) -> Response:
    """El mismo resumen que muestra la pantalla, como archivo.

    Sale del mismo caso de uso de lectura, para que el archivo no pueda decir
    otra cosa que la pantalla.
    """
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        analitica = contenedor.analitica_distributivo(uow.sesion)  # type: ignore[attr-defined]
        caso = ExportarResumenDistributivo(analitica, contenedor.exportadores, contenedor.reloj)
        archivo = await caso(
            EntradaExportarResumen(
                grupo_a=tuple(grupo_a or ()),
                grupo_b=tuple(grupo_b or ()),
                dedicacion_ids=tuple(dedicacion_ids or ()),
                resumen=resumen,
                grupo=grupo,
                etiqueta_a=etiqueta_a,
                etiqueta_b=etiqueta_b,
                formato=formato,
            ),
            contexto,
        )
    return _como_descarga(archivo)


# ===========================================================================
# Carga de un distributivo exportado por el sistema academico
# ===========================================================================

#: Tope del archivo. El PAO mas grande cargado hasta ahora pesa 820 KB; 25 MB
#: deja margen de sobra y evita que una subida equivocada ocupe memoria.
_TOPE_ARCHIVO = 25 * 1024 * 1024

#: Extensiones que acepta el lector. El contenido manda —se mira la firma del
#: archivo, no el nombre—, pero filtrar aqui da un mensaje claro antes de leer.
_EXTENSIONES = (".xls", ".xlsx", ".xlsm")


@router.post(
    "/distributivo/importaciones/pao",
    response_model=ResultadoImportacionSalida,
    summary="Cargar un distributivo exportado por el sistema academico",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_IMPORTAR)],
    responses={422: {"description": "El archivo no tiene la estructura esperada"}},
)
async def importar_pao(
    uow: UowDep,
    contexto: ContextoDep,
    archivo: Annotated[UploadFile, File(description="PAO en formato .xls o .xlsx")],
    semestre: Annotated[
        str, Form(description="Semestre que cubre el archivo, `2026-2`. El archivo no lo trae.")
    ],
    interciclo: Annotated[
        bool, Form(description="Periodo corto entre dos ordinarios: su codigo termina en 0.")
    ] = False,
    actualizar_existentes: Annotated[
        bool,
        Form(
            description=(
                "Actualiza la fila que ya exista con la misma clave natural en vez de rechazarla."
            )
        ),
    ] = True,
    hoja: Annotated[
        str | None, Form(description="Hoja del libro. Por defecto, la primera.")
    ] = None,
) -> ResultadoImportacionSalida:
    """Lee el archivo y carga sus filas.

    Un archivo cubre un semestre, pero produce hasta tres periodos: a cual va
    cada fila lo decide su facultad —tecnologia, grado o posgrado—, igual que
    en la carga por linea de comandos.

    `actualizar_existentes` viene activado por defecto porque el caso habitual
    es recargar un periodo corregido: sin el, la carga se detendria en la
    primera fila ya existente.
    """
    nombre = archivo.filename or "archivo"
    if not nombre.lower().endswith(_EXTENSIONES):
        raise ErrorValidacion(
            f"Se esperaba un archivo {', '.join(_EXTENSIONES)}; llego '{nombre}'",
            campo="archivo",
        )

    contenido = await archivo.read()
    if len(contenido) > _TOPE_ARCHIVO:
        raise ErrorValidacion(
            f"El archivo supera el tope de {_TOPE_ARCHIVO // (1024 * 1024)} MB",
            campo="archivo",
        )

    filas, no_desglosadas = LectorPaoExcel().leer(
        contenido, pao=semestre.strip(), interciclo=interciclo, hoja=hoja or None
    )

    caso = ImportarDistributivo(uow)
    resultado = await caso(
        EntradaImportacion(filas=tuple(filas), reemplazar_existentes=actualizar_existentes),
        contexto,
    )
    return ResultadoImportacionSalida.desde(
        resultado,
        no_desglosadas=no_desglosadas,
        periodo=f"{semestre.strip()}{' interciclo' if interciclo else ''}",
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
            asignaturas_ids=datos.asignaturas_ids,
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
    "/reportes/distributivo/ambito",
    response_model=AmbitoDisponible,
    summary="Facultades y carreras que existen en lo ya elegido",
    dependencies=[requiere(Permiso.DISTRIBUTIVO_LEER)],
)
async def ambito_disponible(
    uow: UowDep,
    contexto: ContextoDep,
    pao_ids: Annotated[list[UUID] | None, Query(description="Periodos academicos")] = None,
    facultad_ids: Annotated[
        list[UUID] | None, Query(description="Facultades ya marcadas. Solo acota las carreras.")
    ] = None,
) -> AmbitoDisponible:
    """El selector encadenado de la pantalla de exportacion.

    Las facultades se acotan por periodo; las carreras, por periodo y facultad.
    Nada de esto sale de una columna del catalogo: doce carreras se dictan en
    dos facultades a la vez, y varias facultades dejaron de existir en la
    reestructuracion de 2026-1 sin desaparecer del historico.
    """
    periodos = tuple(pao_ids or ())
    facultades_marcadas = tuple(facultad_ids or ())

    facultades = await FacultadesDisponibles(uow)(
        EntradaCarrerasDisponibles(pao_ids=periodos), contexto
    )
    carreras = await CarrerasDisponibles(uow)(
        EntradaCarrerasDisponibles(pao_ids=periodos, facultad_ids=facultades_marcadas),
        contexto,
    )
    return AmbitoDisponible(
        facultades=[OpcionSelector.desde(f) for f in facultades],
        carreras=[OpcionSelector.desde(c) for c in carreras],
    )


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
    return _como_descarga(archivo)


def _como_descarga(archivo: ArchivoReporte) -> Response:
    """Respuesta de descarga con el nombre del archivo en la cabecera.

    `filename*` es el que conserva los acentos; `filename` queda de respaldo.
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
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Length",
        },
    )
