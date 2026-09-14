"""Objetos de valor del distributivo docente.

Viven en un modulo aparte de `value_objects.py` porque pertenecen a un contexto
distinto: alli estan los del expediente academico (cedula, correo, periodo de
cobertura), aqui los de la carga horaria docente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import ClassVar, Self

from app.domain.errors import ErrorValidacion
from app.domain.value_objects import Cedula

# ---------------------------------------------------------------------------
# Identificacion del docente
# ---------------------------------------------------------------------------

_PATRON_PASAPORTE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{4,19}$")


@dataclass(frozen=True, slots=True)
class Identificacion:
    """Documento de identidad de un docente.

    A diferencia de `Cedula`, admite pasaporte. El padron real lo exige: cerca
    del 5% de los docentes del distributivo son extranjeros y figuran con
    documentos como `AR920756` o `G04590632`, que no pasan —ni deben pasar— la
    verificacion de modulo 10 del Registro Civil.

    Se conserva `es_cedula` para saber cuando el numero es contrastable contra
    el registro nacional y cuando no.
    """

    valor: str
    es_cedula: bool = False

    def __post_init__(self) -> None:
        limpio = re.sub(r"[\s\-.]", "", (self.valor or "")).upper()
        object.__setattr__(self, "valor", limpio)

        if not limpio:
            raise ErrorValidacion("La identificacion es obligatoria", campo="identificacion")
        if len(limpio) > 20:
            raise ErrorValidacion(
                "La identificacion no puede exceder 20 caracteres", campo="identificacion"
            )

        if Cedula.es_valida(limpio):
            object.__setattr__(self, "es_cedula", True)
            return

        object.__setattr__(self, "es_cedula", False)
        if not _PATRON_PASAPORTE.match(limpio):
            raise ErrorValidacion(
                f"Identificacion invalida: '{limpio}'. Debe ser una cedula "
                "ecuatoriana valida o un documento alfanumerico de 5 a 20 caracteres.",
                campo="identificacion",
            )

    @classmethod
    def es_valida(cls, valor: str) -> bool:
        try:
            cls(valor)
        except ErrorValidacion:
            return False
        return True

    def enmascarada(self) -> str:
        if len(self.valor) < 4:
            return "*" * len(self.valor)
        return f"{self.valor[:2]}{'*' * (len(self.valor) - 4)}{self.valor[-2:]}"

    def __str__(self) -> str:
        return self.valor


# ---------------------------------------------------------------------------
# Periodo academico (PAO)
# ---------------------------------------------------------------------------

_PATRON_PAO = re.compile(r"^(\d{4})\s*-\s*([12])$")

#: El codigo institucional: anio (2), periodo (1), nivel (2) y una constante.
_PATRON_PAO_LARGO = re.compile(r"^(\d{2})([12])(15|65|75)1$")


class NivelPeriodo(StrEnum):
    """Los tres periodos en que se divide cada semestre.

    La institucion planifica por separado la oferta tecnologica, la de grado y
    la de posgrado: un mismo semestre calendario son tres periodos academicos
    distintos, con su propio codigo.
    """

    TECNOLOGIA = "TECNOLOGIA"
    GRADO = "GRADO"
    POSGRADO = "POSGRADO"

    @property
    def digitos(self) -> str:
        """Los dos digitos centrales del codigo."""
        return _DIGITOS_NIVEL[self]

    @property
    def etiqueta(self) -> str:
        """Como se nombra en pantalla, con tilde."""
        return _ETIQUETAS_NIVEL[self]


_DIGITOS_NIVEL: dict[NivelPeriodo, str] = {
    NivelPeriodo.TECNOLOGIA: "15",
    NivelPeriodo.GRADO: "65",
    NivelPeriodo.POSGRADO: "75",
}

_ETIQUETAS_NIVEL: dict[NivelPeriodo, str] = {
    NivelPeriodo.TECNOLOGIA: "TECNOLOGÍA",
    NivelPeriodo.GRADO: "GRADO",
    NivelPeriodo.POSGRADO: "POSGRADO",
}

_POR_DIGITOS: dict[str, NivelPeriodo] = {v: k for k, v in _DIGITOS_NIVEL.items()}


@dataclass(frozen=True, slots=True, order=False)
class PeriodoAcademico:
    """Periodo Academico Ordinario, con su codigo institucional de seis digitos.

    Un semestre calendario —`2026-1`— son **tres** periodos: tecnologia, grado
    y posgrado, que se planifican por separado. El codigo los distingue:

        2 6 1 65 1
        │ │ │ │  └─ constante
        │ │ │ └──── nivel: 15 tecnologia · 65 grado · 75 posgrado
        │ │ └────── periodo del anio (1 o 2)
        └─┴──────── dos ultimos digitos del anio

    Se modela como objeto y no como texto porque hay que **ordenarlo**: el
    reporte deriva el «anio de inicio de actividades en la carrera» del periodo
    mas antiguo en que aparece un docente, y comparar cadenas daria un orden
    correcto por casualidad, no por diseno.
    """

    anio: int
    periodo: int
    nivel: NivelPeriodo = NivelPeriodo.GRADO

    def __post_init__(self) -> None:
        if not 2000 <= self.anio <= 2100:
            raise ErrorValidacion(f"Anio fuera de rango: {self.anio}", campo="pao")
        if self.periodo not in (1, 2):
            raise ErrorValidacion(f"El periodo debe ser 1 o 2, no {self.periodo}", campo="pao")

    @classmethod
    def desde_codigo(cls, codigo: str) -> Self:
        """Acepta el codigo de seis digitos y tambien la forma antigua `2026-1`.

        La forma antigua se sigue admitiendo porque es como viene el PAO en el
        consolidado: quien importa escribe `2026-1` y el nivel sale de las
        columnas FACULTAD y NIVEL de la propia fila.
        """
        limpio = "".join((codigo or "").split())

        largo = _PATRON_PAO_LARGO.match(limpio)
        if largo:
            return cls(
                anio=2000 + int(largo.group(1)),
                periodo=int(largo.group(2)),
                nivel=_POR_DIGITOS[largo.group(3)],
            )

        corto = _PATRON_PAO.match((codigo or "").strip())
        if corto:
            return cls(anio=int(corto.group(1)), periodo=int(corto.group(2)))

        raise ErrorValidacion(
            f"Codigo de PAO invalido: '{codigo}'. Se espera la forma '261651' "
            "—anio, periodo, nivel y constante— o la antigua 'AAAA-N'.",
            campo="pao",
        )

    @property
    def codigo(self) -> str:
        """El codigo institucional: `2026-1` de grado → `261651`."""
        return f"{self.anio % 100:02d}{self.periodo}{self.nivel.digitos}1"

    @property
    def semestre(self) -> str:
        """El semestre calendario, sin el nivel: `2026-1`.

        Es lo que traia el consolidado y lo que vuelve a salir al exportarlo en
        su formato de origen.
        """
        return f"{self.anio}-{self.periodo}"

    @property
    def nombre(self) -> str:
        """Como se lee en pantalla: `2026-1 GRADO`."""
        return f"{self.semestre} {self.nivel.etiqueta}"

    @property
    def orden(self) -> int:
        """Clave numerica para ordenar: `2026-1` → 20261.

        **Deliberadamente no distingue el nivel**: el reporte deriva el anio
        dividiendo entre diez, y los tres periodos de un mismo semestre deben
        seguir dando el mismo anio. Para desempatar entre ellos se ordena
        despues por codigo.
        """
        return self.anio * 10 + self.periodo

    def __lt__(self, otro: PeriodoAcademico) -> bool:
        return (self.orden, self.codigo) < (otro.orden, otro.codigo)

    def __str__(self) -> str:
        return self.nombre


# ---------------------------------------------------------------------------
# Distribucion de horas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DistribucionHoras:
    """Carga horaria de una fila del distributivo, por tipo de actividad.

    El consolidado reparte las horas en cuatro bloques con subactividades:
    docencia (`Da`..`Dn`), gestion (`Ga`..`Gn`), investigacion (`Ia`..`Ij`) y
    vinculacion (`Va`..`Vi`). Los totales son la suma de cada bloque.

    **Sobre el redondeo:** `TotalHoras` se calcula con redondeo bancario
    (`ROUND_HALF_EVEN`), que es el que usan R y Python por defecto y con el que
    se construyo el consolidado historico. Usar HALF_UP produciria diferencias
    de un centesimo contra el archivo de origen, y esas diferencias se leen como
    errores de carga.
    """

    docencia: dict[str, float]
    gestion: dict[str, float]
    investigacion: dict[str, float]
    vinculacion: dict[str, float]

    #: Subactividades de cada bloque, en el orden del consolidado.
    CLAVES_DOCENCIA: ClassVar[tuple[str, ...]] = tuple(f"D{c}" for c in "abcdefghijklmn")
    CLAVES_GESTION: ClassVar[tuple[str, ...]] = tuple(f"G{c}" for c in "abcdefghijklmn")
    CLAVES_INVESTIGACION: ClassVar[tuple[str, ...]] = tuple(f"I{c}" for c in "abcdefghij")
    CLAVES_VINCULACION: ClassVar[tuple[str, ...]] = tuple(f"V{c}" for c in "abcdefghi")

    @classmethod
    def vacia(cls) -> Self:
        return cls(docencia={}, gestion={}, investigacion={}, vinculacion={})

    @classmethod
    def desde_plano(cls, valores: dict[str, float | None]) -> Self:
        """Construye la distribucion desde un diccionario plano `{"Da": 1.0, …}`.

        Los valores ausentes o nulos se omiten en lugar de guardarse como cero:
        el consolidado distingue «no aplica» (celda vacia) de «cero horas», y
        aplanar esa diferencia perderia informacion del origen.
        """

        def bloque(claves: tuple[str, ...]) -> dict[str, float]:
            return {
                k: float(valores[k])  # type: ignore[arg-type]
                for k in claves
                if valores.get(k) is not None
            }

        return cls(
            docencia=bloque(cls.CLAVES_DOCENCIA),
            gestion=bloque(cls.CLAVES_GESTION),
            investigacion=bloque(cls.CLAVES_INVESTIGACION),
            vinculacion=bloque(cls.CLAVES_VINCULACION),
        )

    # ------------------------------------------------------------- totales
    @staticmethod
    def _sumar(bloque: dict[str, float]) -> float:
        return float(sum(bloque.values()))

    @property
    def total_docencia(self) -> float:
        return self._sumar(self.docencia)

    @property
    def total_gestion(self) -> float:
        return self._sumar(self.gestion)

    @property
    def total_investigacion(self) -> float:
        return self._sumar(self.investigacion)

    @property
    def total_vinculacion(self) -> float:
        return self._sumar(self.vinculacion)

    @property
    def total(self) -> float:
        """Total redondeado a dos decimales con redondeo bancario."""
        bruto = (
            self.total_docencia
            + self.total_gestion
            + self.total_investigacion
            + self.total_vinculacion
        )
        return float(Decimal(repr(bruto)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))

    @property
    def esta_vacia(self) -> bool:
        return not (self.docencia or self.gestion or self.investigacion or self.vinculacion)

    def a_plano(self) -> dict[str, float]:
        """Vuelve al diccionario plano, para exportar o comparar con el origen."""
        return {**self.docencia, **self.gestion, **self.investigacion, **self.vinculacion}
