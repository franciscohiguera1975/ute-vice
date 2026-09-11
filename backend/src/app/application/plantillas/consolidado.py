"""Plantilla de origen: el consolidado tal como llego.

Reproduce las 72 columnas del `distributivo.xlsx` original, en su mismo orden,
para poder contrastar lo que guarda el sistema contra el archivo de partida sin
tener que alinear columnas a mano.

Tres advertencias sobre la fidelidad de la reproduccion:

* **Las columnas derivadas se recalculan.** `D`, `G`, `I`, `V` y `TotalHoras` no
  se leyeron al importar —manda el detalle— asi que aqui salen de sumar los
  componentes. Si el archivo de origen traia un total que no cuadraba, la
  comparacion lo delata, que es justamente para lo que sirve.
* **El orden de las columnas de investigacion es el del origen.** `Ic, Ie, Ig,
  Ih, Ii, I, V, Ia, Ib, Id, If, Ij` no tiene logica; es como quedo el archivo y
  se respeta para que las columnas se puedan comparar por posicion.
* **Cinco columnas son residuos del cruce que produjo el archivo** y el sistema
  no las almacena: `NA` (siempre vacia), `an` y `gen` (copias del nombre y del
  genero), `N.x` (contador que vale 1) y `N.y` (numero de titulos del docente).
  Se emiten reconstruidas para que las posiciones calcen; no son dato nuevo.

El texto de los catalogos sale del **codigo**, que conserva como los nombraba el
consolidado, y no del nombre, que la importacion capitaliza para que se lea
mejor en pantalla. De otro modo cada celda de texto figuraria como diferencia
por una simple cuestion de mayusculas.

Quedan dos diferencias reales y esperadas:

* `TITULO` vuelve a unirse con `" & "`. El origen mezclaba ese separador con
  comas, y al importar se separaron en titulos individuales; al rearmarlos se
  usa un unico separador.
* `SEDE` sale normalizada. El consolidado nombraba un mismo campus de varias
  formas —«CAMPUS CUENCA», «CUENCA»— y la importacion las unifico. No hay un
  texto original al que volver, porque eran varios.
"""

from __future__ import annotations

from typing import ClassVar

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.domain.ports.distributivo import FilaDistributivoResuelta, FiltroDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects_distributivo import DistribucionHoras

#: Separador con el que se rearma la celda `TITULO`.
SEPARADOR_TITULOS = " & "

#: Orden exacto de las columnas de horas en el archivo de origen, con los
#: subtotales intercalados donde el archivo los tiene.
_HORAS_EN_ORDEN: tuple[str, ...] = (
    *DistribucionHoras.CLAVES_DOCENCIA,
    "D",
    *DistribucionHoras.CLAVES_GESTION,
    "G",
    "Ic",
    "Ie",
    "Ig",
    "Ih",
    "Ii",
    "I",
    "V",
    "Ia",
    "Ib",
    "Id",
    "If",
    "Ij",
    *DistribucionHoras.CLAVES_VINCULACION,
)

#: Subtotales que se recalculan en lugar de leerse de la fila.
_SUBTOTALES = frozenset({"D", "G", "I", "V"})


def _columnas() -> list[ColumnaReporte]:
    columnas: list[ColumnaReporte] = [
        ColumnaReporte("IDENTIFICACION", "IDENTIFICACION", 14),
        ColumnaReporte("PAO", "PAO", 9, alineacion="centro"),
        ColumnaReporte("FACULTAD", "FACULTAD", 12),
        ColumnaReporte("CARRERA", "CARRERA", 34),
        ColumnaReporte("SEDE", "SEDE", 14),
        ColumnaReporte("APELLIDOS.Y.NOMBRES", "APELLIDOS.Y.NOMBRES", 34),
        ColumnaReporte("TITULARIDAD", "TITULARIDAD", 14),
        ColumnaReporte("DEDICACION", "DEDICACION", 14),
        ColumnaReporte("CATEGORIA", "CATEGORIA", 16),
    ]
    columnas += [
        ColumnaReporte(clave, clave, 7, tipo="numero", alineacion="derecha")
        for clave in _HORAS_EN_ORDEN
    ]
    columnas += [
        ColumnaReporte("NIVEL", "NIVEL", 14),
        ColumnaReporte("CARRERA/PROGRAMA", "CARRERA/PROGRAMA", 34),
        ColumnaReporte("TotalHoras", "TotalHoras", 11, tipo="numero", alineacion="derecha"),
        ColumnaReporte("MEDIDA", "MEDIDA", 34),
        ColumnaReporte("NA", "NA", 6),
        ColumnaReporte("an", "an", 34),
        ColumnaReporte("gen", "gen", 12),
        ColumnaReporte("N.x", "N.x", 6, tipo="numero", alineacion="centro"),
        ColumnaReporte("TITULO", "TITULO", 48),
        ColumnaReporte("TIPOTITULO", "TIPOTITULO", 22),
        ColumnaReporte("GENERO", "GENERO", 12),
        ColumnaReporte("N.y", "N.y", 6, tipo="numero", alineacion="centro"),
    ]
    return columnas


#: Las 72 columnas del consolidado, en el orden del archivo de origen.
COLUMNAS_CONSOLIDADO: list[ColumnaReporte] = _columnas()


class PlantillaConsolidadoOrigen(PlantillaDistributivo):
    """El consolidado con la estructura del archivo original."""

    codigo: ClassVar[str] = "consolidado-origen"
    nombre: ClassVar[str] = "Consolidado (formato original)"
    descripcion: ClassVar[str] = (
        "Las 72 columnas del distributivo.xlsx de origen, en su mismo orden, "
        "para contrastar lo almacenado contra el archivo de partida."
    )
    titulo: ClassVar[str] = "Distributivo consolidado"

    # Sin preambulo ni totales: la cabecera va en la fila 1, como en el origen.
    # Es lo que permite abrir los dos archivos y compararlos directamente.
    solo_datos: ClassVar[bool] = True

    async def construir(
        self,
        uow: UnidadDeTrabajo,
        filtro: FiltroDistributivo,
        *,
        incluir_auditoria: bool = False,
        limite: int | None = None,
    ) -> ContenidoPlantilla:
        filas = await uow.distributivo.filas_resueltas(filtro)
        visibles = filas[:limite] if limite else filas

        return ContenidoPlantilla(
            columnas=COLUMNAS_CONSOLIDADO,
            filas=[self._a_fila(f) for f in visibles],
            total_filas=len(filas),
            total_docentes=len({f.docente_identificacion for f in filas}),
            sin_asignatura=sum(1 for f in filas if f.fila.requiere_asignatura),
            totales={
                "Registros": len(filas),
                "Docentes": len({f.docente_identificacion for f in filas}),
                "Total de horas": round(sum(f.fila.total_horas for f in filas), 2),
            },
        )

    def _a_fila(self, r: FilaDistributivoResuelta) -> dict[str, object]:
        horas = r.fila.horas
        plano = horas.a_plano()
        subtotales = {
            "D": horas.total_docencia,
            "G": horas.total_gestion,
            "I": horas.total_investigacion,
            "V": horas.total_vinculacion,
        }

        fila: dict[str, object] = {
            "IDENTIFICACION": r.docente_identificacion,
            "PAO": r.pao,
            "FACULTAD": r.facultad,
            "CARRERA": r.codigo_carrera or r.carrera,
            "SEDE": r.codigo_sede or r.sede,
            "APELLIDOS.Y.NOMBRES": r.docente_nombre,
            "TITULARIDAD": r.codigo_titularidad or r.titularidad,
            "DEDICACION": r.codigo_dedicacion or r.dedicacion,
            "CATEGORIA": r.codigo_categoria or r.categoria,
        }
        for clave in _HORAS_EN_ORDEN:
            fila[clave] = subtotales[clave] if clave in _SUBTOTALES else plano.get(clave)

        fila.update(
            {
                "NIVEL": r.codigo_nivel or r.nivel,
                "CARRERA/PROGRAMA": r.codigo_programa or r.programa,
                "TotalHoras": r.fila.total_horas,
                "MEDIDA": r.fila.medida,
                # Residuos del cruce que produjo el archivo original; se
                # reconstruyen para que las columnas calcen por posicion.
                "NA": None,
                "an": r.docente_nombre,
                "gen": r.codigo_genero or r.genero,
                "N.x": 1,
                "TITULO": SEPARADOR_TITULOS.join(r.titulos) if r.titulos else None,
                "TIPOTITULO": r.codigo_tipo_titulo or r.tipo_titulo,
                "GENERO": r.codigo_genero or r.genero,
                "N.y": len(r.titulos),
            }
        )
        return fila
