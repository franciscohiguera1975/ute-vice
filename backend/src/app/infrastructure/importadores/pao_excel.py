"""Lectura del distributivo tal como lo exporta el sistema academico.

Es un formato distinto del consolidado: 74 o 75 columnas, cabeceras propias, y
la sede, el nivel y la modalidad en columnas separadas en lugar de concatenadas
dentro del nombre de la carrera.

Aporta seis datos que el consolidado no tenia —estado de validacion, fase,
semanas, relacion laboral y las dos marcas de tutoria— y **no trae el PAO**: el
periodo lo indica quien importa, porque el archivo cubre uno solo. Desde
2026-2 tambien trae `Periodo`, que si lo dice fila a fila; ver mas abajo.

## Dos presentaciones de la misma hoja «Distributivo»

El sistema academico exporta la hoja sola —cabecera en la primera fila— o como
parte del reporte completo del PAO, con las demas pestanas del informe:
`Antecedentes`, `Distribucion horaria`, `Excepcionalidades`... En ese reporte
la hoja `Distributivo` no es la primera, asi que sin `hoja` de por medio no se
adivina por posicion: se busca por nombre y, si no aparece, se usa la primera
—lo que hacen los archivos que solo traen esa pestana—. Ahi la cabecera baja
un par de filas (antes va un titulo) y se parte en dos niveles:
`Titularidad`, `Categoria`, `Dedicacion` y `Relacion Laboral` aparecen dos
veces, agrupadas bajo `Antigua` y `Nueva`. Las dos dicen lo mismo salvo por
espacios sueltos, pero donde difieren de verdad `Nueva` trae el dato que
`Antigua` deja en `N/A`, asi que es la que se usa; `Antigua` se descarta
entera. La cabecera no se asume en una fila fija: se busca la primera fila
que trae `Identificacion`, `Facultad` y `Carrera/Programa`, agrupando con la
fila siguiente las columnas que la traen partida.

## El nombre de la carrera

El consolidado escribe `UIO:MEDICINA - GRADO - PRESENCIAL`. Aqui llegan las
cuatro piezas por separado y se recomponen en esa misma forma, para que una
carrera cargada por las dos vias sea la misma y no dos.

## Carrera vacia

Algunas filas —tipicamente de Ciencias de la Salud, con horas reales y estado
de validacion— no traen ninguna carrera: la asignacion todavia no se hizo en
el sistema academico. En vez de descartar al docente, la carrera queda
`SIN CARRERA ASIGNADA`: un valor de catalogo real y filtrable, no una fila
perdida.

## Filas que combinan varias carreras, sedes o periodos

El origen une con comas cuando una sola carga de horas cuenta para mas de una
carrera, sede o periodo a la vez:

    Carrera/Programa = ALIMENTOS, ELECTROMECANICA, INGENIERIA INDUSTRIAL
    Sede             = SEDE QUITO, SEDE SANTO DOMINGO
    Periodo          = 262751, 262651

Las horas vienen como un total unico que no se reparte entre las
combinaciones: la institucion confirmo que cuentan completas en cada una
—un docente que junta grado y posgrado dicta en los dos, no la mitad en
cada uno—. Por eso la fila se **explota**: una `FilaCrudaDistributivo` por
cada combinacion de carrera x sede x periodo, todas con la misma carga,
compartiendo `grupo_combinado_id`. Quien suma horas por docente en lugar de
por carrera o periodo debe agrupar por ese id para no contarla varias veces;
quien suma por carrera o por periodo no necesita hacer nada distinto, porque
cada combinacion es ahi una carga real.

Cuando carrera y sede traen varias a la vez —5 filas en el primer archivo de
2026-2— no hay forma de saber cual iba con cual: se generan **todas** las
combinaciones posibles en lugar de adivinar un emparejamiento, y el aviso que
acompana a la fila lo marca `ambiguo` para que se pueda revisar.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from io import BytesIO
from itertools import product
from pathlib import Path
from typing import Any
from uuid import uuid4

import xlrd
from openpyxl import load_workbook

from app.core.logging import get_logger
from app.domain.errors import ErrorValidacion
from app.domain.ports.importacion import (
    AvisoCombinacion,
    DatosSistemaAcademico,
    FilaCrudaDistributivo,
)
from app.domain.value_objects_distributivo import DistribucionHoras, PeriodoAcademico

log = get_logger(__name__)

#: Nombre de facultad del sistema academico → sigla del consolidado. Sin esto
#: cada facultad entraria dos veces, con su nombre largo y con su sigla.
FACULTADES: dict[str, str] = {
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

#: Sede del sistema academico → prefijo con que el consolidado nombra la
#: carrera. `UIO:MEDICINA - GRADO - PRESENCIAL`.
PREFIJO_SEDE: dict[str, str] = {
    "SEDE QUITO": "UIO",
    "SEDE SANTO DOMINGO": "STO",
    "CAMPUS CUENCA": "CUE",
    "RICARDO HIDALGO OTTOLENGHI": "MON",
}

#: Categoria del sistema academico → la del consolidado. El ERP antepone
#: «TITULAR» a las tres categorias del escalafon; el consolidado no. Sin esta
#: traduccion cada una entraria dos veces y un conteo por categoria saldria
#: partido en dos grupos donde hay uno.
CATEGORIAS: dict[str, str] = {
    "TITULAR AUXILIAR": "AUXILIAR",
    "TITULAR AUXILIAR 1": "AUXILIAR",
    "TITULAR AGREGADO": "AGREGADO",
    "TITULAR PRINCIPAL": "PRINCIPAL",
}

#: El texto del estado tal como lo escribe el origen → valor del enum.
ESTADOS: dict[str, str] = {
    "OK": "OK",
    "OK, EXCEPCIÓN": "OK_EXCEPCION",
    "OK, EXCEPCION": "OK_EXCEPCION",
    "VALIDACIÓN PENDIENTE": "PENDIENTE",
    "VALIDACION PENDIENTE": "PENDIENTE",
    "ERROR": "ERROR",
}

_CLAVES_HORAS = (
    DistribucionHoras.CLAVES_DOCENCIA
    + DistribucionHoras.CLAVES_GESTION
    + DistribucionHoras.CLAVES_INVESTIGACION
    + DistribucionHoras.CLAVES_VINCULACION
)

#: Lo que el origen escribe cuando no hay dato.
_AUSENTES = {"", "N/A", "NA", "0", "-"}

#: Carrera de una fila que aun no tiene asignacion en el sistema academico.
#: Ver la nota del modulo, «Carrera vacia».
SIN_CARRERA = "SIN CARRERA ASIGNADA"


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return " ".join(str(valor).split())


def _o_nada(valor: Any) -> str | None:
    limpio = _texto(valor).upper()
    return None if limpio in _AUSENTES else _texto(valor)


def _lista(valor: Any) -> list[str]:
    """Parte una celda que puede traer varios valores separados por comas.

    Devuelve una lista vacia si la celda no tiene nada, para que quien la use
    decida el valor por defecto (`None`, o un marcador como `SIN_CARRERA`).
    """
    limpio = _texto(valor)
    if limpio.upper() in _AUSENTES:
        return []
    return [p.strip() for p in limpio.split(",") if p.strip()]


#: Columnas sin las que no se puede ubicar la cabecera ni construir una fila.
_OBLIGATORIAS = ("Identificación", "Facultad", "Carrera/Programa")

#: Cuantas filas se recorren buscando la cabecera antes de rendirse. El reporte
#: completo del PAO trae dos filas de titulo antes; un margen generoso no pesa
#: en un archivo de un solo periodo.
_TOPE_FILAS_CABECERA = 20

#: Los grupos con que el reporte completo parte en dos la fila de cabecera.
#: `NUEVA` es el que se usa: ver la nota del modulo.
_GRUPOS_CABECERA = {"ANTIGUA", "NUEVA"}
_GRUPO_VIGENTE = "NUEVA"


def _combinar_cabecera(
    primaria: tuple[Any, ...], secundaria: tuple[Any, ...]
) -> tuple[dict[str, int], bool]:
    """Arma el mapa nombre de columna → posicion de una fila de cabecera.

    En la hoja suelta cada columna trae su nombre directo en `primaria`. En el
    reporte completo, un tramo de columnas queda bajo un rotulo de grupo
    (`Antigua` o `Nueva`) y el nombre real esta en `secundaria`, una fila mas
    abajo — la primera columna del tramo lleva el rotulo del grupo *y* su
    propio nombre a la vez, una encima de la otra. Se descarta el tramo
    `Antigua` entero: ver la nota del modulo.

    Devuelve tambien si se uso `secundaria`: si es asi, esa fila era parte de
    la cabecera y no un dato.
    """
    columnas: dict[str, int] = {}
    uso_secundaria = False
    grupo: str | None = None

    def _de_secundaria(i: int) -> None:
        nonlocal uso_secundaria
        if grupo == _GRUPO_VIGENTE and i < len(secundaria):
            sub = _texto(secundaria[i])
            if sub:
                columnas[sub] = i
                uso_secundaria = True

    for i, valor in enumerate(primaria):
        texto = _texto(valor)
        if not texto:
            _de_secundaria(i)
            continue
        mayusculas = texto.upper()
        if mayusculas in _GRUPOS_CABECERA:
            grupo = mayusculas
            _de_secundaria(i)
            continue
        grupo = None
        columnas[texto] = i
    return columnas, uso_secundaria


def _cabecera(filas: list[tuple[Any, ...]]) -> tuple[dict[str, int], int]:
    """Ubica la fila de cabecera y devuelve `(columnas, primera_fila_de_datos)`.

    No se asume en una posicion fija: la hoja suelta la trae en la primera
    fila, el reporte completo un par de filas mas abajo, detras de su titulo.
    """
    limite = min(len(filas), _TOPE_FILAS_CABECERA)
    for indice in range(limite):
        siguiente = filas[indice + 1] if indice + 1 < len(filas) else ()
        columnas, uso_secundaria = _combinar_cabecera(filas[indice], siguiente)
        if all(o in columnas for o in _OBLIGATORIAS):
            return columnas, indice + (2 if uso_secundaria else 1)
    raise ErrorValidacion(
        f"Al archivo le falta alguna de estas columnas: {', '.join(_OBLIGATORIAS)}. "
        f"Se esperaba la estructura del distributivo que exporta el sistema academico.",
        campo="archivo",
    )


#: Firma de un documento OLE2, que es lo que realmente son los `.xls` que
#: exporta el sistema academico. Se mira el contenido y no la extension porque
#: el origen tambien entrega `.xlsx` con nombre `.xls`.
_FIRMA_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


#: Nombre de la hoja que trae la carga horaria en el reporte completo del PAO.
_HOJA_DISTRIBUTIVO = "distributivo"


def _elegir_hoja(nombres: Sequence[str], hoja: str | None) -> str:
    """Sin hoja explicita, busca `Distributivo` por nombre antes de asumir la primera.

    El reporte completo trae diez pestanas y `Distributivo` no es la primera
    (`Antecedentes` lo es); adivinar por posicion la perderia.
    """
    if hoja:
        return hoja
    for nombre in nombres:
        if nombre.strip().lower() == _HOJA_DISTRIBUTIVO:
            return nombre
    return nombres[0]


def _filas_xlsx(datos: bytes, hoja: str | None) -> Iterator[tuple[Any, ...]]:
    libro = load_workbook(BytesIO(datos), read_only=True, data_only=True)
    try:
        pagina = libro[_elegir_hoja(libro.sheetnames, hoja)]
        yield from pagina.iter_rows(values_only=True)
    finally:
        libro.close()


def _filas_xls(datos: bytes, hoja: str | None) -> Iterator[tuple[Any, ...]]:
    """Formato Excel 97-2003, que openpyxl no lee.

    El sistema academico exporta en este formato, asi que convertirlo a mano
    antes de cargarlo seria un paso manual en cada importacion.
    """
    libro = xlrd.open_workbook(file_contents=datos)
    pagina = libro.sheet_by_name(_elegir_hoja(libro.sheet_names(), hoja))
    for numero in range(pagina.nrows):
        yield tuple(pagina.row_values(numero))


def _filas_del_libro(origen: str | Path | bytes, hoja: str | None) -> Iterator[tuple[Any, ...]]:
    if isinstance(origen, bytes):
        datos = origen
    else:
        camino = Path(origen)
        if not camino.exists():
            raise ErrorValidacion(f"El archivo no existe: {camino}", campo="archivo")
        datos = camino.read_bytes()

    if not datos:
        raise ErrorValidacion("El archivo esta vacio", campo="archivo")

    try:
        if datos[:8] == _FIRMA_OLE2:
            yield from _filas_xls(datos, hoja)
        else:
            yield from _filas_xlsx(datos, hoja)
    except ErrorValidacion:
        raise
    except Exception as exc:  # el motivo lo pone la libreria que abre el libro
        raise ErrorValidacion(
            f"No se pudo leer el archivo como hoja de calculo: {exc}", campo="archivo"
        ) from exc


class LectorPaoExcel:
    """Convierte el distributivo del sistema academico en filas planas."""

    def leer(
        self,
        origen: str | Path | bytes,
        *,
        pao: str,
        interciclo: bool = False,
        hoja: str | None = None,
    ) -> tuple[list[FilaCrudaDistributivo], list[AvisoCombinacion]]:
        """Devuelve `(filas, combinadas)`.

        `origen` es una ruta o el contenido del archivo. Acepta bytes para que
        la carga desde la interfaz no tenga que escribir un temporal en disco.

        `pao` es el semestre —`2026-2`—, que el archivo no trae. `combinadas`
        trae un aviso por cada fila del origen que se exploto en varias filas
        —ver la nota del modulo—; no son rechazos, cuentan como parte de
        `filas`.
        """
        # Se materializa: la cabecera puede estar a un par de filas de
        # distancia y hay que poder mirar hacia adelante para ubicarla. Un PAO
        # entero cabe de sobra en memoria — el mas grande cargado pesa 820 KB.
        libro = list(_filas_del_libro(origen, hoja))
        if not libro:
            raise ErrorValidacion("El archivo esta vacio", campo="archivo")

        col, inicio = _cabecera(libro)
        columna_identificacion = col["Identificación"]

        filas: list[FilaCrudaDistributivo] = []
        combinadas: list[AvisoCombinacion] = []

        for numero, cruda in enumerate(libro[inicio:], start=inicio + 1):
            identificacion = (
                _texto(cruda[columna_identificacion]) if columna_identificacion < len(cruda) else ""
            )
            if not identificacion:
                continue

            explotadas = self._filas(numero, cruda, col, pao, interciclo)
            filas.extend(explotadas)
            if len(explotadas) > 1:
                carreras = _lista(self._valor(cruda, col, "Carrera/Programa"))
                sedes = _lista(self._valor(cruda, col, "Sede"))
                combinadas.append(
                    AvisoCombinacion(
                        numero_fila=numero,
                        identificacion=identificacion,
                        combinaciones=len(explotadas),
                        ambiguo=len(carreras) > 1 and len(sedes) > 1,
                    )
                )

        log.info(
            "Distributivo del sistema academico leido",
            extra={"filas": len(filas), "combinadas": len(combinadas), "pao": pao},
        )
        return filas, combinadas

    # ------------------------------------------------------------------ fila
    @staticmethod
    def _valor(cruda: tuple[Any, ...], col: dict[str, int], nombre: str) -> str:
        posicion = col.get(nombre)
        if posicion is None or posicion >= len(cruda):
            return ""
        return _texto(cruda[posicion])

    def _filas(
        self,
        numero: int,
        cruda: tuple[Any, ...],
        col: dict[str, int],
        pao: str,
        interciclo: bool,
    ) -> list[FilaCrudaDistributivo]:
        """Una fila del origen, explotada en una por cada combinacion.

        Carrera, sede y periodo pueden traer varios valores en la misma celda.
        Ninguno se reparte —el total de horas es unico—; cada combinacion se
        convierte en su propia fila con la misma carga. Ver la nota del modulo.
        """

        def valor(nombre: str) -> str:
            return self._valor(cruda, col, nombre)

        carreras = _lista(valor("Carrera/Programa")) or [SIN_CARRERA]
        sedes_crudas = _lista(valor("Sede"))
        sedes: list[str | None] = list(sedes_crudas) if sedes_crudas else [None]
        periodos = self._periodos(valor("Periodo"))

        combinaciones = list(product(carreras, sedes, periodos))
        grupo_id = uuid4() if len(combinaciones) > 1 else None

        facultad = valor("Facultad").upper()
        horas = {clave: self._numero(cruda, col, clave) for clave in _CLAVES_HORAS if clave in col}
        nivel_columna = valor("Nivel")
        modalidad = valor("Modalidad")
        sistema = DatosSistemaAcademico(
            estado_validacion=ESTADOS.get(valor("Estado de la Validación").upper()),
            fase=_o_nada(valor("Fase")),
            semanas=self._entero(valor("N.º Semanas")),
            relacion_laboral=_o_nada(valor("Relación Laboral")),
            tutor_posgrado=valor("Tutores Posgrado").upper() in {"SÍ", "SI"},
            tutor_medicina=valor("Tutores Medicina").upper() in {"SÍ", "SI"},
            # Distinto de `estado_validacion`: este es el avance de la
            # contratacion administrativa («Aprobado», «En revisión por
            # DGA»…), no la validacion academica de la carga horaria.
            estado_lote=_o_nada(valor("Estado de Lote/Proceso")),
            estado_contrato=_o_nada(valor("Estado de Contrato")),
        )

        return [
            FilaCrudaDistributivo(
                numero_fila=numero,
                identificacion=valor("Identificación"),
                pao=pao,
                facultad=FACULTADES.get(facultad, facultad),
                carrera=self._carrera(
                    carrera, sede or "", nivel_del_periodo or nivel_columna, modalidad
                ),
                sede=_o_nada(sede) if sede else None,
                nombre=valor("Apellidos y Nombres"),
                titularidad=_o_nada(valor("Titularidad")),
                dedicacion=_o_nada(valor("Dedicación")),
                categoria=self._categoria(valor("Categoría")),
                nivel=_o_nada(nivel_del_periodo or nivel_columna),
                medida=_o_nada(valor("Medida")),
                horas=horas,
                interciclo=interciclo,
                sistema=sistema,
                grupo_combinado_id=grupo_id,
            )
            for carrera, sede, nivel_del_periodo in combinaciones
        ]

    @staticmethod
    def _periodos(crudo: str) -> list[str | None]:
        """Los codigos de `Periodo`, traducidos al nivel que cada uno implica.

        Con uno solo —el caso de casi todas las filas— no hay nada que decidir:
        se deja `None` para que la fila use la columna `Nivel` como siempre.
        Con varios, cada codigo fuerza el nivel de su copia —`clasificar_periodo`
        lo respeta igual que si viniera de la columna `Nivel`—, que es lo que
        hace que la explosion caiga en periodos distintos y no en el mismo tres
        veces.
        """
        codigos = _lista(crudo)
        if len(codigos) <= 1:
            return [None]

        niveles: list[str | None] = []
        for codigo in codigos:
            try:
                niveles.append(PeriodoAcademico.desde_codigo(codigo).nivel.value)
            except ErrorValidacion:
                # Un codigo que no se reconoce no debe tumbar toda la fila: se
                # ignora esa copia y se conservan las demas.
                continue
        return niveles or [None]

    @staticmethod
    def _categoria(valor: str) -> str | None:
        limpio = _o_nada(valor)
        return CATEGORIAS.get((limpio or "").upper(), limpio) if limpio else None

    @staticmethod
    def _carrera(carrera: str, sede: str, nivel: str, modalidad: str) -> str | None:
        """Recompone `SEDE:NOMBRE - NIVEL - MODALIDAD`, como el consolidado.

        Sin prefijo de sede conocido se deja el nombre solo: es lo que hace el
        consolidado con las carreras que no lo llevan, como `MEDICINA (R)`.
        """
        if not carrera or carrera.upper() in _AUSENTES:
            return None
        prefijo = PREFIJO_SEDE.get(sede.upper())
        partes = [p for p in (nivel, modalidad) if p and p.upper() not in _AUSENTES]
        nombre = f"{prefijo}:{carrera}" if prefijo else carrera
        return " - ".join([nombre, *partes]) if partes else nombre

    @staticmethod
    def _numero(cruda: tuple[Any, ...], col: dict[str, int], clave: str) -> float:
        try:
            return float(cruda[col[clave]] or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _entero(valor: str) -> int | None:
        try:
            return int(float(valor))
        except (TypeError, ValueError):
            return None
