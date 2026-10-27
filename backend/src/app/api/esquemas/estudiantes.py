"""Esquemas de entrada y salida de la matricula estudiantil."""

from __future__ import annotations

from app.api.esquemas.comunes import EsquemaBase
from app.domain.ports.importacion_estudiantes import ResultadoImportacionEstudiantes


class FilaRechazadaEstudianteSalida(EsquemaBase):
    numero_fila: int
    cedula: str
    motivo: str


class ResultadoImportacionEstudiantesSalida(EsquemaBase):
    total_filas_leidas: int
    estudiantes_creados: int
    estudiantes_existentes: int
    matriculas_creadas: int
    matriculas_actualizadas: int
    becas_creadas: int
    generos_creados: int
    #: Filas cuya `CARRERA` no coincidio por igualdad exacta con ningun
    #: elemento de `cat_carreras`. No se rechazaron ni crearon una carrera
    #: nueva: solo quedaron sin `carrera_id`.
    sin_carrera_reconocida: int
    #: Filas que repetian la clave natural de una matricula ya vista en el
    #: mismo archivo -casi siempre una beca adicional sin concatenar en la
    #: misma celda- y se fusionaron con ella en vez de contarse aparte.
    filas_combinadas_por_duplicado: int
    rechazadas: list[FilaRechazadaEstudianteSalida]
    exitosa: bool
    resumen: str

    @classmethod
    def desde(cls, r: ResultadoImportacionEstudiantes) -> ResultadoImportacionEstudiantesSalida:
        return cls(
            total_filas_leidas=r.total_filas_leidas,
            estudiantes_creados=r.estudiantes_creados,
            estudiantes_existentes=r.estudiantes_existentes,
            matriculas_creadas=r.matriculas_creadas,
            matriculas_actualizadas=r.matriculas_actualizadas,
            becas_creadas=r.becas_creadas,
            generos_creados=r.generos_creados,
            sin_carrera_reconocida=r.sin_carrera_reconocida,
            filas_combinadas_por_duplicado=r.filas_combinadas_por_duplicado,
            # Se recorta a 200, igual que en la importacion del distributivo:
            # un archivo mal exportado puede rechazar miles de filas.
            rechazadas=[
                FilaRechazadaEstudianteSalida(
                    numero_fila=e.numero_fila, cedula=e.cedula, motivo=e.motivo
                )
                for e in r.rechazadas[:200]
            ],
            exitosa=r.exitosa,
            resumen=r.resumen(),
        )
