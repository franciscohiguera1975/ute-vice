"""Plantilla institucional: reporte de indicadores docentes.

Reproduce las veinte columnas de `Reporte_Docentes.xlsx`: las mismas doce
columnas de docente, carrera y condicion contractual que ya resuelve
`PlantillaDocenciaPorCarrera` (ver `docencia.py`), mas el detalle de horas por
funcion —docencia total, solo impartir clase, investigacion, vinculacion y
gestion— que alimenta despues los indicadores institucionales (Relacion D/Da,
porcentaje de horas por funcion). Esos indicadores **no se calculan aqui**:
esta plantilla entrega el detalle por docente, no el resumen agregado.

Igual que en `docencia.py`, las columnas se agrupan en dos colores de
cabecera: identificacion y el bloque de resultado (`M` a `T`) en un color, y
las columnas de insumo (`B` a `L`) en otro.
"""

from __future__ import annotations

from typing import ClassVar

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.domain.ports.distributivo import FilaReporteIndicadoresDocentes, FiltroDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.ports.uow import UnidadDeTrabajo

#: Colores de la plantilla: gris para el insumo (B-L, igual que en
#: `docencia.py`) y azul para el resultado (A y M-T), que es el bloque que
#: alimenta los indicadores institucionales.
_GRIS = "D9D9D9"
_AZUL = "BDD7EE"

#: Las veinte columnas de `Reporte_Docentes.xlsx`, en su orden literal.
COLUMNAS_INDICADORES_DOCENTES: list[ColumnaReporte] = [
    ColumnaReporte("identificacion", "Identificación", 14, color_cabecera=_AZUL),
    ColumnaReporte("nombre", "Nombre ", 34, color_cabecera=_GRIS),
    ColumnaReporte("titulo_profesional", "Título Profesional ", 40, color_cabecera=_GRIS),
    ColumnaReporte(
        "grado_academico", "Grado académico más alto completado", 24, color_cabecera=_GRIS
    ),
    ColumnaReporte("asignatura", "Asignatura que imparte", 32, color_cabecera=_GRIS),
    ColumnaReporte(
        "anio_inicio_carrera",
        "Año de inicio de actividades en la carrera",
        16,
        tipo="numero",
        alineacion="centro",
        color_cabecera=_GRIS,
    ),
    ColumnaReporte("jerarquia_docente", "Jerarquía Docente", 18, color_cabecera=_GRIS),
    ColumnaReporte("dedicacion_horaria", "Dedicación horaria contratada", 20, color_cabecera=_GRIS),
    ColumnaReporte("tipo_contrato", "Tipo de contrato", 16, color_cabecera=_GRIS),
    ColumnaReporte("unidad", "Unidad a la que pertenece", 28, color_cabecera=_GRIS),
    ColumnaReporte("comuna", "Comuna", 16, color_cabecera=_GRIS),
    ColumnaReporte(
        "anio_actual", "Año actual", 10, tipo="numero", alineacion="centro", color_cabecera=_GRIS
    ),
    ColumnaReporte(
        "total_horas",
        "Total de horas",
        13,
        tipo="numero",
        alineacion="derecha",
        color_cabecera=_AZUL,
    ),
    ColumnaReporte(
        "total_da", "Total_Da", 11, tipo="numero", alineacion="derecha", color_cabecera=_AZUL
    ),
    ColumnaReporte(
        "total_d", "Total_D", 11, tipo="numero", alineacion="derecha", color_cabecera=_AZUL
    ),
    ColumnaReporte(
        "total_i", "Total_I", 11, tipo="numero", alineacion="derecha", color_cabecera=_AZUL
    ),
    ColumnaReporte(
        "total_v", "Total_V", 11, tipo="numero", alineacion="derecha", color_cabecera=_AZUL
    ),
    ColumnaReporte(
        "total_g", "Total_G", 11, tipo="numero", alineacion="derecha", color_cabecera=_AZUL
    ),
    ColumnaReporte("medida", "Medida", 10, color_cabecera=_AZUL),
    ColumnaReporte("genero", "Género", 12, color_cabecera=_AZUL),
]


class PlantillaIndicadoresDocentes(PlantillaDistributivo):
    """Reproduce `Reporte_Docentes.xlsx`: detalle de horas por funcion y docente."""

    codigo: ClassVar[str] = "indicadores-docentes"
    nombre: ClassVar[str] = "Reporte de indicadores docentes"
    descripcion: ClassVar[str] = (
        "Detalle de horas por función —docencia, impartir clase, investigación, "
        "vinculación y gestión— por docente, en el formato de Reporte_Docentes.xlsx."
    )
    titulo: ClassVar[str] = "Reporte de indicadores docentes"

    # Sin preambulo ni totales: reproduce un archivo institucional de origen,
    # igual que `PlantillaConsolidadoOrigen`.
    solo_datos: ClassVar[bool] = True

    async def construir(
        self,
        uow: UnidadDeTrabajo,
        filtro: FiltroDistributivo,
        *,
        incluir_auditoria: bool = False,
        limite: int | None = None,
    ) -> ContenidoPlantilla:
        filas = await uow.distributivo.filas_para_reporte_indicadores(filtro)
        visibles = filas[:limite] if limite else filas

        return ContenidoPlantilla(
            columnas=list(COLUMNAS_INDICADORES_DOCENTES),
            filas=[self._a_fila(f) for f in visibles],
            total_filas=len(filas),
            total_docentes=len({f.identificacion for f in filas}),
            sin_asignatura=sum(1 for f in filas if f.total_d > 0 and not f.asignatura),
            sin_anio_inicio=sum(1 for f in filas if f.anio_inicio_carrera is None),
            totales={
                "Docentes": len({f.identificacion for f in filas}),
                "Registros": len(filas),
                "Total de horas": round(sum(f.total_horas for f in filas), 2),
            },
        )

    @staticmethod
    def _a_fila(f: FilaReporteIndicadoresDocentes) -> dict[str, object]:
        return {
            "identificacion": f.identificacion,
            "nombre": f.nombre,
            "titulo_profesional": f.titulo_profesional,
            "grado_academico": f.grado_academico,
            "asignatura": f.asignatura,
            "anio_inicio_carrera": f.anio_inicio_carrera,
            "jerarquia_docente": f.jerarquia_docente,
            "dedicacion_horaria": f.dedicacion_horaria,
            "tipo_contrato": f.tipo_contrato,
            "unidad": f.unidad,
            "comuna": f.comuna,
            "anio_actual": f.anio_actual,
            "total_horas": f.total_horas,
            "total_da": f.total_da,
            "total_d": f.total_d,
            "total_i": f.total_i,
            "total_v": f.total_v,
            "total_g": f.total_g,
            "medida": f.medida,
            "genero": f.genero,
        }
