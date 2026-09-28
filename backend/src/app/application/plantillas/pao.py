"""Plantilla de origen: el distributivo tal como lo exporta el sistema academico.

Reproduce la hoja `Distributivo` que trae el reporte del sistema academico desde
2026-2 —sola o dentro del reporte completo del PAO—, en el mismo orden de
columnas con que la lee `LectorPaoExcel`, para poder contrastar lo que guarda
el sistema contra el archivo que lo actualizo sin alinear columnas a mano.

Advertencias sobre la fidelidad de la reproduccion, en el mismo espiritu que
las de `consolidado.py`:

* **Tres columnas del origen no se leyeron al importar y no se emiten**: las
  dos razones (`(Db + Dh)/Da`, `(D-Da)/Da`) y el bloque `Antigua` completo (el
  sistema solo guarda `Nueva`; ver el modulo del lector). `Da Total` y
  `Total Horas` del origen son ademas duplicados de `Da` y de
  `Total Horas Semestrales`: tampoco se reproducen aparte.
* **`Sede` sale normalizada** (`QUITO`, `SANTO DOMINGO`, `MON`, `CUENCA`) en
  lugar de `SEDE QUITO`, `CAMPUS CUENCA`, etc. Es la misma normalizacion del
  consolidado y no hay vuelta atras: varias formas del origen caen en el mismo
  codigo.
* **`Facultad` vuelve a su nombre largo por un diccionario fijo** —el inverso
  del que usa el lector—: si el origen trae una facultad que no esta en ese
  diccionario, sale tal como la guardo el sistema.
* **`Carrera/Programa` y `Modalidad` se separan de nuevo** deshaciendo la
  composicion `SEDE:NOMBRE - NIVEL - MODALIDAD` que arma el lector. Es una
  reconstruccion textual: si el nombre de la carrera contuviera el separador
  ` - `, la separacion podria fallar. No ocurre en el padron actual.
* **`Categoria`** vuelve a anteponer «TITULAR» a las tres categorias del
  escalafon. Es una aproximacion, no una inversa exacta: el origen tambien
  escribe `TITULAR AUXILIAR 1` para la misma categoria, y esa variante no se
  puede distinguir de `TITULAR AUXILIAR` una vez importada.
* **`Fase`, `Relación Laboral`, `Estado de la Validación`, `Estado de
  Lote/Proceso` y `Estado de Contrato` salen en mayusculas o con la redaccion
  del catalogo**, no con la capitalizacion exacta del origen (`Planificación`
  sale `PLANIFICACIÓN`). Es cosmetico: el dato es el mismo.
"""

from __future__ import annotations

from typing import ClassVar

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.domain.enums import EstadoValidacion
from app.domain.ports.distributivo import FilaDistributivoResuelta, FiltroDistributivo
from app.domain.ports.reportes import ColumnaReporte
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects_distributivo import DistribucionHoras

#: Orden exacto de las columnas de horas en el archivo de origen: docencia,
#: investigacion, vinculacion y gestion —**no** el orden D-G-I-V del
#: consolidado—, con el subtotal de cada bloque donde el archivo lo trae.
_HORAS_EN_ORDEN: tuple[str, ...] = (
    *DistribucionHoras.CLAVES_DOCENCIA,
    "D",
    *DistribucionHoras.CLAVES_INVESTIGACION,
    "I",
    *DistribucionHoras.CLAVES_VINCULACION,
    "V",
    *DistribucionHoras.CLAVES_GESTION,
    "G",
)

_SUBTOTALES = frozenset({"D", "G", "I", "V"})

#: Nombre de facultad del sistema academico → sigla del consolidado, tal como
#: lo aplica `LectorPaoExcel`. Se repite aqui, invertido, porque la plantilla
#: no depende de la capa de infraestructura: solo el lector importa el archivo
#: original, la plantilla solo reconstruye su forma.
_FACULTADES: dict[str, str] = {
    "CIENCIAS DE LA SALUD EUGENIO ESPEJO": "FCSEE",
    "POSGRADOS EN LÍNEA": "PEL",
    "CIENCIAS DE LA INGENIERÍA E INDUSTRIAS": "FCII",
    "DERECHO, CIENCIAS ADMINISTRATIVAS Y SOCIALES": "FDCAS",
    "MEDICINA VETERINARIA Y AGRONOMÍA": "FMVA",
    "ARQUITECTURA Y URBANISMO": "FAU",
    "CIENCIAS GASTRONÓMICAS Y TURISMO": "FCGT",
    "UNIDAD ACADÉMICA ESPECIALIZADA EN LA FORMACIÓN TÉCNICA Y TECNOLÓGICA": "UAEFTT",
    "CIENCIAS, INGENIERÍA Y CONSTRUCCIÓN": "FCIC",
    "CENTRO DE EDUCACIÓN EN LÍNEA": "CEL",
    "ODONTOLOGÍA": "FO",
}
_SIGLA_A_FACULTAD: dict[str, str] = {v: k for k, v in _FACULTADES.items()}

#: Categoria del consolidado → la que antepone «TITULAR» el sistema academico.
#: Inversa aproximada de `CATEGORIAS` en el lector: no distingue
#: `TITULAR AUXILIAR` de `TITULAR AUXILIAR 1`, que el lector funde en una sola.
_CATEGORIA_A_ERP: dict[str, str] = {
    "AUXILIAR": "TITULAR AUXILIAR",
    "AGREGADO": "TITULAR AGREGADO",
    "PRINCIPAL": "TITULAR PRINCIPAL",
}

#: Estado de validacion del dominio → el texto con que lo escribe el origen.
_ESTADO_A_TEXTO: dict[EstadoValidacion, str] = {
    EstadoValidacion.OK: "OK",
    EstadoValidacion.OK_EXCEPCION: "OK, EXCEPCIÓN",
    EstadoValidacion.PENDIENTE: "VALIDACIÓN PENDIENTE",
    EstadoValidacion.ERROR: "ERROR",
}


def _columnas() -> list[ColumnaReporte]:
    columnas: list[ColumnaReporte] = [
        ColumnaReporte("No.", "No.", 6, tipo="numero", alineacion="centro"),
        ColumnaReporte("Identificación", "Identificación", 14),
        ColumnaReporte("Apellidos y Nombres", "Apellidos y Nombres", 34),
        ColumnaReporte("Sede", "Sede", 16),
        ColumnaReporte("Nivel", "Nivel", 12),
        ColumnaReporte("Facultad", "Facultad", 40),
        ColumnaReporte("Carrera/Programa", "Carrera/Programa", 34),
        ColumnaReporte("Modalidad", "Modalidad", 14),
    ]
    columnas += [
        ColumnaReporte(clave, clave, 7, tipo="numero", alineacion="derecha")
        for clave in _HORAS_EN_ORDEN
    ]
    columnas += [
        ColumnaReporte(
            "Total Horas Semanales",
            "Total Horas Semanales",
            12,
            tipo="numero",
            alineacion="derecha",
        ),
        ColumnaReporte(
            "Total Horas Semestrales",
            "Total Horas Semestrales",
            14,
            tipo="numero",
            alineacion="derecha",
        ),
        ColumnaReporte("Tutores Posgrado", "Tutores Posgrado", 10, alineacion="centro"),
        ColumnaReporte("Tutores Medicina", "Tutores Medicina", 10, alineacion="centro"),
        ColumnaReporte("Medida", "Medida", 34),
        ColumnaReporte("Titularidad", "Titularidad", 14),
        ColumnaReporte("Categoría", "Categoría", 18),
        ColumnaReporte("Dedicación", "Dedicación", 16),
        ColumnaReporte("Relación Laboral", "Relación Laboral", 20),
        ColumnaReporte("Estado de la Validación", "Estado de la Validación", 20),
        ColumnaReporte("Estado de Lote/Proceso", "Estado de Lote/Proceso", 20),
        ColumnaReporte("Estado de Contrato", "Estado de Contrato", 18),
        ColumnaReporte("N.º Semanas", "N.º Semanas", 10, tipo="numero", alineacion="centro"),
        ColumnaReporte("Fase", "Fase", 16),
    ]
    return columnas


#: Las columnas que el sistema puede reconstruir del archivo del sistema
#: academico, en el orden en que aparecen alli.
COLUMNAS_PAO: list[ColumnaReporte] = _columnas()


def _separar_carrera(codigo_carrera: str, codigo_nivel: str | None) -> tuple[str, str | None]:
    """Deshace `SEDE:NOMBRE - NIVEL - MODALIDAD`, el inverso de `_carrera()`.

    `codigo_nivel` es el que ya trae la fila por su cuenta, asi que no hay que
    adivinar cual de los tramos separados por ` - ` es el nivel: se busca ese
    valor exacto y todo lo que sigue es la modalidad.
    """
    resto = codigo_carrera.split(":", 1)[1] if ":" in codigo_carrera else codigo_carrera

    if not codigo_nivel:
        # Sin nivel, `_carrera()` solo pudo haber agregado la modalidad.
        if " - " in resto:
            nombre, modalidad = resto.rsplit(" - ", 1)
            return nombre, modalidad
        return resto, None

    sufijo_solo_nivel = f" - {codigo_nivel}"
    if resto.endswith(sufijo_solo_nivel):
        return resto[: -len(sufijo_solo_nivel)], None

    marcador = f" - {codigo_nivel} - "
    posicion = resto.find(marcador)
    if posicion != -1:
        return resto[:posicion], resto[posicion + len(marcador) :]

    # El nivel no aparece donde `_carrera()` lo habria puesto: no se puede
    # separar con certeza. Se deja el nombre completo y la modalidad vacia en
    # lugar de arriesgar un corte equivocado.
    return resto, None


class PlantillaPaoOrigen(PlantillaDistributivo):
    """El distributivo con la estructura del reporte del sistema academico."""

    codigo: ClassVar[str] = "pao-origen"
    nombre: ClassVar[str] = "Distributivo (formato sistema académico)"
    descripcion: ClassVar[str] = (
        "Las columnas del distributivo que exporta el sistema académico, en su "
        "mismo orden, para contrastar lo almacenado contra el archivo que "
        "actualizó el periodo."
    )
    titulo: ClassVar[str] = "Distributivo del sistema académico"

    # Sin preambulo ni totales: la cabecera va en la fila 1, como en el origen.
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
            columnas=COLUMNAS_PAO,
            filas=[self._a_fila(numero, f) for numero, f in enumerate(visibles, start=1)],
            total_filas=len(filas),
            total_docentes=len({f.docente_identificacion for f in filas}),
            sin_asignatura=sum(1 for f in filas if f.fila.requiere_asignatura),
            totales={
                "Registros": len(filas),
                "Docentes": len({f.docente_identificacion for f in filas}),
                "Total de horas": round(sum(f.fila.total_horas for f in filas), 2),
            },
        )

    def _a_fila(self, numero: int, r: FilaDistributivoResuelta) -> dict[str, object]:
        horas = r.fila.horas
        plano = horas.a_plano()
        subtotales = {
            "D": horas.total_docencia,
            "G": horas.total_gestion,
            "I": horas.total_investigacion,
            "V": horas.total_vinculacion,
        }

        codigo_carrera = r.codigo_carrera or r.carrera
        codigo_nivel = r.codigo_nivel or r.nivel
        carrera_programa, modalidad = _separar_carrera(codigo_carrera, codigo_nivel)

        fila: dict[str, object] = {
            # Secuencial de salida: el origen tambien es solo un consecutivo de
            # fila, no un identificador que sobreviva entre archivos.
            "No.": numero,
            "Identificación": r.docente_identificacion,
            "Apellidos y Nombres": r.docente_nombre,
            "Sede": r.codigo_sede or r.sede,
            "Nivel": codigo_nivel,
            "Facultad": _SIGLA_A_FACULTAD.get(r.facultad, r.facultad),
            "Carrera/Programa": carrera_programa,
            "Modalidad": modalidad,
        }
        for clave in _HORAS_EN_ORDEN:
            fila[clave] = subtotales[clave] if clave in _SUBTOTALES else plano.get(clave)

        semanas = r.fila.semanas
        estado = r.fila.estado_validacion

        fila.update(
            {
                "Total Horas Semanales": r.fila.total_horas,
                "Total Horas Semestrales": (
                    round(r.fila.total_horas * semanas, 2) if semanas is not None else None
                ),
                "Tutores Posgrado": "Sí" if r.fila.tutor_posgrado else "No",
                "Tutores Medicina": "Sí" if r.fila.tutor_medicina else "No",
                "Medida": r.fila.medida,
                "Titularidad": r.codigo_titularidad or r.titularidad,
                "Categoría": _CATEGORIA_A_ERP.get(
                    r.codigo_categoria or r.categoria or "", r.codigo_categoria or r.categoria
                ),
                "Dedicación": r.codigo_dedicacion or r.dedicacion,
                "Relación Laboral": r.fila.relacion_laboral,
                "Estado de la Validación": (
                    _ESTADO_A_TEXTO.get(estado, estado.value) if estado else None
                ),
                "Estado de Lote/Proceso": r.fila.estado_lote,
                "Estado de Contrato": r.fila.estado_contrato,
                "N.º Semanas": semanas,
                "Fase": r.fila.fase,
            }
        )
        return fila
