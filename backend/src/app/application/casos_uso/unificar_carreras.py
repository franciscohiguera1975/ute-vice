"""Unificacion de carreras que son la misma con nombres distintos.

El catalogo acumulo variantes de un mismo programa porque cada origen lo
escribia a su manera y ninguno mandaba sobre el anterior:

    INGENIERÍA MECATRÓNICA                  2020-1 … 2020-2
    MECATRÓNICA                             2020-1 … 2022-2
    MECATRÓNICA (R) - PRESENCIAL            2023-1 … 2025-2
    UIO:MECATRÓNICA - GRADO - PRESENCIAL    2026-1

Un informe por carrera sale partido en cuatro donde hay una.

## Por que no basta un UPDATE

La clave natural de una fila es docente, periodo, carrera y sede. Al reasignar,
dos filas del mismo docente que estaban en variantes distintas del mismo periodo
pasan a compartir clave. En mecatronica ocurre en 19 casos.

Esas filas **se fusionan sumando sus horas**, que es lo mismo que hace la
importacion cuando el origen repite una clave: el total es el dato que la
institucion reporta. Sus asignaturas se unen, sin repetir.

## Que no hace

No decide **cuales** son la misma carrera. Esa comparacion no se puede
automatizar sin equivocarse: `UIO:ARQUITECTURA - POSGRADO - HÍBRIDA` y
`ARQUITECTURA (R) - PRESENCIAL` comparten el nombre desnudo y son programas
distintos. Las variantes las indica quien ejecuta.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.core.logging import get_logger
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.entities.distributivo import FilaDistributivo
from app.domain.enums import Permiso
from app.domain.errors import ErrorValidacion, NoEncontrado
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects_distributivo import DistribucionHoras

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EntradaUnificarCarreras:
    destino: str
    """Codigo de la carrera que se conserva."""

    variantes: tuple[str, ...]
    """Codigos que se absorben. Desaparecen del catalogo."""


@dataclass(slots=True)
class FusionDeFilas:
    """Dos o mas filas que quedaron con la misma clave natural al unificar."""

    identificacion: str
    periodo: str
    horas_previas: tuple[float, ...]
    horas_resultantes: float


@dataclass(slots=True)
class ResultadoUnificacion:
    filas_reasignadas: int = 0
    filas_fusionadas: int = 0
    variantes_retiradas: int = 0
    fusiones: list[FusionDeFilas] = field(default_factory=list)


class UnificarCarreras(CasoDeUso[EntradaUnificarCarreras, ResultadoUnificacion]):
    """Deja una sola carrera donde habia varias con el mismo significado."""

    nombre = "catalogos.unificar_carreras"
    descripcion = "Unifica varias carreras del catalogo en una sola"
    permiso_requerido = Permiso.CATALOGOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaUnificarCarreras, contexto: ContextoEjecucion
    ) -> ResultadoUnificacion:
        if not entrada.variantes:
            raise ErrorValidacion("No hay variantes que unificar", campo="variantes")
        if entrada.destino in entrada.variantes:
            raise ErrorValidacion(
                "La carrera de destino no puede estar entre las variantes", campo="destino"
            )

        resultado = ResultadoUnificacion()

        async with self._uow:
            destino = await self._uow.catalogos.obtener_por_codigo(
                TipoCatalogo.CARRERA, entrada.destino
            )
            if destino is None:
                raise NoEncontrado("carrera", entrada.destino)

            ids_variantes = []
            for codigo in entrada.variantes:
                elemento = await self._uow.catalogos.obtener_por_codigo(
                    TipoCatalogo.CARRERA, codigo
                )
                if elemento is None:
                    raise NoEncontrado("carrera", codigo)
                ids_variantes.append(elemento.id)

            afectadas = await self._uow.distributivo.filas_de_carreras([destino.id, *ids_variantes])

            # Agrupadas por lo que sera su clave natural tras la reasignacion.
            por_clave: defaultdict[tuple[UUID, UUID, UUID | None], list[FilaDistributivo]] = (
                defaultdict(list)
            )
            for fila in afectadas:
                por_clave[(fila.docente_id, fila.pao_id, fila.sede_id)].append(fila)

            conservar: list[FilaDistributivo] = []
            eliminar: list[UUID] = []

            for grupo in por_clave.values():
                # Se conserva la que ya estaba en el destino, si la hay: asi su
                # identificador sobrevive y con el las materias enlazadas.
                grupo.sort(key=lambda f: (f.carrera_id != destino.id, f.id.hex))
                principal, resto = grupo[0], grupo[1:]

                if principal.carrera_id != destino.id:
                    principal.carrera_id = destino.id
                    resultado.filas_reasignadas += 1

                if resto:
                    resultado.filas_fusionadas += len(resto)
                    previas = tuple(f.total_horas for f in grupo)
                    principal.horas = self._sumar(grupo)
                    principal.asignaturas_ids = self._unir_asignaturas(grupo)
                    eliminar.extend(f.id for f in resto)
                    resultado.fusiones.append(
                        FusionDeFilas(
                            identificacion=str(principal.docente_id),
                            periodo=str(principal.pao_id),
                            horas_previas=previas,
                            horas_resultantes=principal.horas.total,
                        )
                    )

                conservar.append(principal)

            # Primero se borran las absorbidas: mientras existan, la clave
            # natural de la que se conserva seguiria ocupada.
            for fila_id in eliminar:
                await self._uow.distributivo.eliminar(fila_id)
            for fila in conservar:
                await self._uow.distributivo.actualizar(fila)

            for elemento_id in ids_variantes:
                await self._uow.catalogos.eliminar(TipoCatalogo.CARRERA, elemento_id)
                resultado.variantes_retiradas += 1

            await self._uow.commit()

        log.info(
            "Carreras unificadas",
            extra={
                "destino": entrada.destino,
                "variantes": len(entrada.variantes),
                "reasignadas": resultado.filas_reasignadas,
                "fusionadas": resultado.filas_fusionadas,
            },
        )
        return resultado

    @staticmethod
    def _sumar(grupo: list[FilaDistributivo]) -> DistribucionHoras:
        acumulado: defaultdict[str, float] = defaultdict(float)
        for fila in grupo:
            for clave, valor in fila.horas.a_plano().items():
                acumulado[clave] += valor
        return DistribucionHoras.desde_plano(dict(acumulado))

    @staticmethod
    def _unir_asignaturas(grupo: list[FilaDistributivo]) -> list[UUID]:
        vistas: list[UUID] = []
        for fila in grupo:
            for asignatura in fila.asignaturas_ids:
                if asignatura not in vistas:
                    vistas.append(asignatura)
        return vistas
