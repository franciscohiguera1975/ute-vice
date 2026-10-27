"""Endpoints de la matricula estudiantil."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.dependencias import ContextoDep, UowDep, requiere
from app.api.esquemas.estudiantes import ResultadoImportacionEstudiantesSalida
from app.application.casos_uso.importar_estudiantes import (
    EntradaImportacionEstudiantes,
    ImportarEstudiantes,
)
from app.domain.enums import Permiso
from app.domain.errors import ErrorValidacion
from app.infrastructure.importadores.estudiantes_excel import LectorEstudiantesExcel

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])

#: El reporte mas grande visto hasta ahora pesa unos pocos MB; 25 MB deja
#: margen de sobra, igual que en la carga del distributivo.
_TOPE_ARCHIVO = 25 * 1024 * 1024

#: El contenido manda -se mira la cabecera del archivo, no el nombre-, pero
#: filtrar aqui da un mensaje claro antes de leer.
_EXTENSIONES = (".xlsx", ".xlsm")


@router.post(
    "/importaciones",
    response_model=ResultadoImportacionEstudiantesSalida,
    summary="Cargar un reporte de matricula estudiantil",
    dependencies=[requiere(Permiso.ESTUDIANTES_IMPORTAR)],
    responses={422: {"description": "El archivo no tiene la estructura esperada"}},
)
async def importar(
    uow: UowDep,
    contexto: ContextoDep,
    archivo: Annotated[
        UploadFile,
        File(description=("Reporte de matricula de Banner (.xlsx), hoja RptEstBannerMatriculas")),
    ],
) -> ResultadoImportacionEstudiantesSalida:
    """Lee el archivo y carga sus filas.

    A diferencia del distributivo docente, no se pide el periodo aparte: el
    reporte de Banner trae el padron completo vigente, con `PERIODO` como una
    columna mas de cada fila, asi que no hace falta que quien importa lo
    indique.
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

    filas = LectorEstudiantesExcel().leer(contenido)

    caso = ImportarEstudiantes(uow)
    resultado = await caso(EntradaImportacionEstudiantes(filas=tuple(filas)), contexto)
    return ResultadoImportacionEstudiantesSalida.desde(resultado)
