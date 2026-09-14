"""Carga de las materias que imparte cada docente.

El reporte de origen agrupa por **docente y semestre**; el distributivo se
organiza por docente, periodo, carrera y sede. Falta un dato para unir las dos
cosas sin ambiguedad, y el archivo no lo tiene.

La regla que se aplica: **las materias de un docente en un semestre se enlazan a
todas sus filas de ese semestre**. Es lo que pide el informe —«las materias por
periodo de cada docente»— y es honesto con lo que el origen sabe. Repartirlas
entre carreras exigiria adivinar cual materia pertenece a cual, y una atribucion
inventada es peor que una lista completa.

Cuando el archivo declara el nivel del periodo —`261651` es grado, `261751`
posgrado— se usa para acotar el destino a las filas de ese nivel. Solo resuelve
una parte de los casos, pero los que resuelve los resuelve bien.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.casos_uso.importar_distributivo import CacheDeCatalogos
from app.core.logging import get_logger
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.enums import Permiso
from app.domain.ports.importacion import (
    FilaCrudaMateria,
    MateriaSinDestino,
    ResultadoImportacionMaterias,
)
from app.domain.ports.uow import UnidadDeTrabajo

log = get_logger(__name__)

#: Los dos digitos del codigo institucional que nombran el nivel.
#:
#: El SICAF numera la tecnologia con `55` y el sistema con `15`. La diferencia
#: es una decision tomada, no un error: se conserva el `15` del Vicerrectorado
#: porque es el de los periodos ya emitidos y los informes que ya circularon
#: (ver `_DIGITOS_NIVEL`). Aqui se traduce, que es el unico sitio donde entran
#: codigos ajenos.
_NIVELES = {"55": "15", "15": "15", "65": "65", "75": "75"}


@dataclass(frozen=True, slots=True)
class EntradaImportacionMaterias:
    filas: tuple[FilaCrudaMateria, ...]


def prefijo_de_semestre(semestre: str) -> str | None:
    """`2026-1` → `261`, los tres primeros digitos del codigo del periodo.

    Devuelve `None` para lo que no sea un semestre: el reporte trae tambien
    `2025` y `2026` a secas, que son educacion continua y no tienen periodo
    academico al que pertenecer.
    """
    partes = semestre.split("-")
    if len(partes) != 2:
        return None
    anio, periodo = partes[0].strip(), partes[1].strip()
    if not (anio.isdigit() and periodo.isdigit()):
        return None
    return f"{int(anio) % 100:02d}{periodo}"


def identificaciones(celda: str) -> list[str]:
    """Las cedulas de una celda, que puede traer varias.

    Una materia dictada por dos profesores llega con las dos cedulas unidas por
    punto y coma —`1712…; 1718…`—, y a veces con la misma repetida, que es como
    el origen anota la codocencia. La materia es de todos ellos: se separa y se
    enlaza a cada uno. Sin esto se perdian 1.728 filas, el 10 % del reporte.
    """
    vistas: list[str] = []
    for parte in celda.replace(",", ";").split(";"):
        limpia = parte.strip()
        if limpia and limpia not in vistas:
            vistas.append(limpia)
    return vistas


def primer_nombre(celda: str) -> str:
    """El primero de los nombres cuando la celda trae varios docentes."""
    return celda.split(";")[0].strip()


def nivel_declarado(codigo_periodo: str) -> str | None:
    """Los dos digitos de nivel del codigo institucional, si los trae."""
    limpio = codigo_periodo.strip()
    if len(limpio) != 6 or not limpio.isdigit():
        return None
    return _NIVELES.get(limpio[3:5])


class ImportarMaterias(CasoDeUso[EntradaImportacionMaterias, ResultadoImportacionMaterias]):
    """Enlaza las materias del reporte con las filas del distributivo.

    Politica de fallos: una materia que no encuentra destino no aborta la carga.
    Se informa agrupada por docente, porque el caso interesante —alguien que
    dicta y no consta en el distributivo— se lee mejor por persona que por fila.
    """

    nombre = "distributivo.importar_materias"
    descripcion = "Importa las materias que imparte cada docente"
    permiso_requerido = Permiso.DISTRIBUTIVO_IMPORTAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaImportacionMaterias, contexto: ContextoEjecucion
    ) -> ResultadoImportacionMaterias:
        resultado = ResultadoImportacionMaterias(total_filas_leidas=len(entrada.filas))

        async with self._uow:
            catalogos = CacheDeCatalogos(self._uow)
            await catalogos.cargar()
            ya_existian = catalogos.conocidas(TipoCatalogo.ASIGNATURA)

            indice = _Indice(await self._uow.distributivo.indice_para_materias())

            # fila del distributivo -> nombres de materia, sin repetir
            por_fila: defaultdict[UUID, set[str]] = defaultdict(set)
            huerfanas: defaultdict[tuple[str, str], int] = defaultdict(int)
            nombres: dict[tuple[str, str], str] = {}
            sin_periodo: Counter[str] = Counter()

            for fila in entrada.filas:
                prefijo = prefijo_de_semestre(fila.semestre)
                if prefijo is None:
                    sin_periodo[fila.semestre] += 1
                    continue

                nivel = nivel_declarado(fila.codigo_periodo)
                materia = " ".join(fila.materia.split())

                for identificacion in identificaciones(fila.identificacion):
                    destinos = indice.destinos(identificacion, prefijo, nivel)
                    if not destinos:
                        clave = (identificacion, fila.semestre)
                        huerfanas[clave] += 1
                        nombres.setdefault(clave, primer_nombre(fila.nombre_docente))
                        continue
                    for destino in destinos:
                        por_fila[destino].add(materia)

            # Se ordenan alfabeticamente: el orden del enlace es el que sale en
            # la celda del reporte, y un orden estable hace comparables dos
            # exportaciones del mismo periodo.
            enlaces = {
                fila_id: [
                    id_asignatura
                    for nombre in sorted(materias)
                    if (id_asignatura := catalogos.resolver(TipoCatalogo.ASIGNATURA, nombre))
                ]
                for fila_id, materias in por_fila.items()
            }

            await catalogos.persistir()
            resultado.enlaces_creados = await self._uow.distributivo.enlazar_asignaturas(enlaces)
            await self._uow.commit()

        resultado.filas_enlazadas = len(enlaces)
        resultado.asignaturas_creadas = catalogos.creados[TipoCatalogo.ASIGNATURA.value]
        resultado.asignaturas_existentes = ya_existian
        resultado.semestres_sin_periodo = dict(sin_periodo)
        resultado.sin_destino = sorted(
            (
                MateriaSinDestino(
                    identificacion=ident,
                    nombre_docente=nombres[(ident, semestre)],
                    semestre=semestre,
                    materias=cuantas,
                )
                for (ident, semestre), cuantas in huerfanas.items()
            ),
            key=lambda m: (-m.materias, m.identificacion),
        )

        log.info(
            "Materias importadas",
            extra={
                "filas": resultado.total_filas_leidas,
                "enlaces": resultado.enlaces_creados,
                "sin_destino": resultado.materias_sin_destino,
            },
        )
        return resultado


class _Indice:
    """Filas del distributivo por docente y semestre."""

    def __init__(self, filas: list[tuple[UUID, str, str]]) -> None:
        self._por_clave: defaultdict[tuple[str, str], list[tuple[UUID, str]]] = defaultdict(list)
        for fila_id, identificacion, codigo_pao in filas:
            # Los tres primeros digitos del codigo son anio y periodo; los dos
            # siguientes, el nivel.
            self._por_clave[(identificacion, codigo_pao[:3])].append((fila_id, codigo_pao[3:5]))

    def destinos(self, identificacion: str, prefijo: str, nivel: str | None) -> list[UUID]:
        candidatas = self._por_clave.get((identificacion, prefijo), [])
        if nivel is not None:
            del_nivel = [f for f, n in candidatas if n == nivel]
            # Si el nivel no acierta ninguna, se conserva el resto: el origen y
            # el distributivo pueden discrepar en como clasificaron a un
            # docente, y perder la materia por eso seria peor.
            if del_nivel:
                return del_nivel
        return [f for f, _ in candidatas]
