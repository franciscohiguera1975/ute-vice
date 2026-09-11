"""Contrato de una plantilla de exportacion del distributivo.

Una plantilla decide **tres cosas**: que columnas salen, de donde se sacan las
filas y como se numeran. Todo lo demas —resolver los filtros, elegir el formato
del archivo, controlar el tamano— es igual para todas y vive en el caso de uso.

Separarlo asi permite agregar una plantilla nueva escribiendo una clase y
registrandola, sin tocar el caso de uso, el router ni el frontend: la interfaz
pregunta por las plantillas disponibles y pinta lo que reciba.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from app.domain.ports.distributivo import FiltroDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.ports.uow import UnidadDeTrabajo


@dataclass(frozen=True, slots=True)
class ContenidoPlantilla:
    """Lo que una plantilla produce para un filtro dado."""

    columnas: list[ColumnaReporte]

    #: Las filas que se entregan. Con `limite`, solo las primeras.
    filas: list[dict[str, object]]

    #: Cuantas filas cumplen el filtro, con limite o sin el.
    total_filas: int = 0
    total_docentes: int = 0

    #: Cuantas filas dictan clase y no tienen asignatura registrada. Es el dato
    #: que obliga a completar informacion antes de enviar el archivo.
    sin_asignatura: int = 0

    #: Cuantas filas no tienen anio de inicio derivable. Solo aplica a las
    #: plantillas que lo incluyen.
    sin_anio_inicio: int = 0

    #: Totales que el exportador imprime al pie.
    totales: dict[str, object] = field(default_factory=dict)


class PlantillaDistributivo(ABC):
    """Una forma concreta de exportar el distributivo.

    Las subclases declaran su identidad como atributos de clase para que el
    registro pueda listarlas sin instanciarlas.
    """

    #: Identificador estable. Viaja en la peticion y en la URL, asi que no se
    #: cambia una vez publicado.
    codigo: ClassVar[str]
    nombre: ClassVar[str]
    descripcion: ClassVar[str]

    #: Encabezado del archivo generado.
    titulo: ClassVar[str]

    #: `True` si tiene sentido ofrecer las columnas de auditoria al final.
    admite_auditoria: ClassVar[bool] = False

    #: `True` para exportar sin preambulo ni totales, con la cabecera en la
    #: primera fila. Lo piden las plantillas que reproducen un archivo ajeno.
    solo_datos: ClassVar[bool] = False

    @abstractmethod
    async def construir(
        self,
        uow: UnidadDeTrabajo,
        filtro: FiltroDistributivo,
        *,
        incluir_auditoria: bool = False,
        limite: int | None = None,
    ) -> ContenidoPlantilla:
        """Arma columnas y filas. `limite` lo usa la vista previa."""
        ...
