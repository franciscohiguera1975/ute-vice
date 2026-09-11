"""Plantilla institucional: cuerpo docente por carrera.

Reproduce el formato que exige la institucion —el de `tabla_excel.png`—: una
fila por docente y carrera, con las cinco primeras columnas resaltadas en
amarillo y el resto en gris.

Dos de las doce columnas se derivan y no estan en el consolidado:

* **Anio de inicio de actividades en la carrera** — el periodo mas antiguo en que
  ese docente aparece en esa carrera, calculado sobre **todo** el historico y no
  solo sobre el periodo que se esta exportando.
* **Titulo profesional** — el primero de los titulos del docente. El consolidado
  los concatena en una sola celda y el primero suele ser el grado base; los
  posgrados los reporta aparte la columna de grado academico.

Y una no existe en ninguna parte del origen: **asignatura que imparte**. El
distributivo reparte horas por tipo de actividad, no por materia. Se captura a
mano y, mientras nadie la complete, la columna viaja vacia en lugar de
rellenarse con un dato inventado.

El reporte informa cuantas filas la necesitan, contando solo las que **dictan
clase**: a quien tiene toda su carga en gestion o investigacion no le falta
ninguna asignatura. Es la misma regla que usa la pantalla de captura, para que
el numero que avisa aqui sea el que aparece alla.
"""

from __future__ import annotations

from typing import ClassVar

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.domain.ports.distributivo import FilaReporteDocencia, FiltroDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.ports.uow import UnidadDeTrabajo

#: Colores de la plantilla institucional.
_AMARILLO = "FFFF00"
_GRIS = "D9D9D9"

#: Las doce columnas, en el orden y con el color de la plantilla.
COLUMNAS_DOCENCIA: list[ColumnaReporte] = [
    ColumnaReporte(
        "numero", "N °", 6, tipo="numero", alineacion="centro", color_cabecera=_AMARILLO
    ),
    ColumnaReporte("nombre", "Nombre", 34, color_cabecera=_AMARILLO),
    ColumnaReporte("titulo_profesional", "Título Profesional", 40, color_cabecera=_AMARILLO),
    ColumnaReporte(
        "grado_academico", "Grado Académico más alto completado", 24, color_cabecera=_AMARILLO
    ),
    ColumnaReporte("asignatura", "Asignatura que imparte", 32, color_cabecera=_AMARILLO),
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
]

#: Columnas opcionales para contrastar el reporte contra el distributivo.
_AUDITORIA: list[ColumnaReporte] = [
    ColumnaReporte("identificacion", "Identificación", 14),
    ColumnaReporte("carrera", "Carrera", 34),
    ColumnaReporte("total_horas", "Total horas", 12, tipo="numero", alineacion="derecha"),
]


class PlantillaDocenciaPorCarrera(PlantillaDistributivo):
    """Formato institucional de cuerpo docente por carrera."""

    codigo: ClassVar[str] = "docencia-carrera"
    nombre: ClassVar[str] = "Cuerpo docente por carrera"
    descripcion: ClassVar[str] = (
        "Formato institucional de doce columnas: docente, título, grado académico, "
        "asignatura y condición contractual."
    )
    titulo: ClassVar[str] = "Cuerpo docente por carrera"
    admite_auditoria: ClassVar[bool] = True

    async def construir(
        self,
        uow: UnidadDeTrabajo,
        filtro: FiltroDistributivo,
        *,
        incluir_auditoria: bool = False,
        limite: int | None = None,
    ) -> ContenidoPlantilla:
        filas = await uow.distributivo.filas_para_reporte(filtro)

        columnas = list(COLUMNAS_DOCENCIA)
        if incluir_auditoria:
            columnas += _AUDITORIA

        sin_asignatura = sum(1 for f in filas if f.requiere_asignatura)
        return ContenidoPlantilla(
            columnas=columnas,
            filas=[self._a_fila(f) for f in (filas[:limite] if limite else filas)],
            total_filas=len(filas),
            total_docentes=len({f.identificacion for f in filas}),
            sin_asignatura=sin_asignatura,
            sin_anio_inicio=sum(1 for f in filas if f.anio_inicio_carrera is None),
            totales=self._totales(filas, sin_asignatura),
        )

    @staticmethod
    def _a_fila(f: FilaReporteDocencia) -> dict[str, object]:
        return {
            "numero": f.numero,
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
            "identificacion": f.identificacion,
            "carrera": f.carrera,
            "total_horas": f.total_horas,
        }

    @staticmethod
    def _totales(filas: list[FilaReporteDocencia], sin_asignatura: int) -> dict[str, object]:
        totales: dict[str, object] = {
            "Docentes": len({f.identificacion for f in filas}),
            "Registros": len(filas),
        }
        if sin_asignatura:
            totales["Sin asignatura registrada"] = sin_asignatura
        return totales
