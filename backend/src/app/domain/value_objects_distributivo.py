"""Objetos de valor del distributivo docente.

Viven en un modulo aparte de `value_objects.py` porque pertenecen a un contexto
distinto: alli estan los del expediente academico (cedula, correo, periodo de
cobertura), aqui los de la carga horaria docente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
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


@dataclass(frozen=True, slots=True)
class PeriodoAcademico:
    """Periodo Academico Ordinario, en la forma `2026-1`.

    Se modela como objeto y no como texto porque hay que **ordenarlo**: el
    reporte deriva el «anio de inicio de actividades en la carrera» del periodo
    mas antiguo en que aparece un docente, y comparar cadenas daria un orden
    correcto por casualidad, no por diseno.
    """

    anio: int
    periodo: int

    def __post_init__(self) -> None:
        if not 2000 <= self.anio <= 2100:
            raise ErrorValidacion(f"Anio fuera de rango: {self.anio}", campo="pao")
        if self.periodo not in (1, 2):
            raise ErrorValidacion(f"El periodo debe ser 1 o 2, no {self.periodo}", campo="pao")

    @classmethod
    def desde_codigo(cls, codigo: str) -> Self:
        coincidencia = _PATRON_PAO.match((codigo or "").strip())
        if not coincidencia:
            raise ErrorValidacion(
                f"Codigo de PAO invalido: '{codigo}'. Se espera la forma 'AAAA-N', "
                "por ejemplo '2026-1'.",
                campo="pao",
            )
        return cls(anio=int(coincidencia.group(1)), periodo=int(coincidencia.group(2)))

    @property
    def codigo(self) -> str:
        return f"{self.anio}-{self.periodo}"

    @property
    def orden(self) -> int:
        """Clave numerica para ordenar: `2026-1` → 20261."""
        return self.anio * 10 + self.periodo

    def __lt__(self, otro: PeriodoAcademico) -> bool:
        return self.orden < otro.orden

    def __str__(self) -> str:
        return self.codigo


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
