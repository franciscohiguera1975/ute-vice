"""Objetos de valor: inmutables, autovalidados y comparables por contenido.

Al declarar un parametro como `Cedula` en vez de `str`, la validacion deja de
ser una responsabilidad que cada llamador debe recordar: si tienes una instancia
de `Cedula`, ya esta validada. Esa es la razon de que existan estos tipos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Self

from app.domain.errors import ErrorValidacion

# ---------------------------------------------------------------------------
# Cedula ecuatoriana
# ---------------------------------------------------------------------------

_COEFICIENTES_CEDULA = (2, 1, 2, 1, 2, 1, 2, 1, 2)
_PROVINCIAS_VALIDAS = frozenset(range(1, 25)) | {30}
"""01–24 son las provincias; 30 identifica a ecuatorianos en el exterior."""


@dataclass(frozen=True, slots=True)
class Cedula:
    """Cedula de identidad ecuatoriana de 10 digitos, con digito verificador.

    Se valida con el algoritmo de modulo 10 publicado por el Registro Civil. Una
    cedula que no pasa la verificacion nunca llega al proveedor externo: se
    descarta antes, y eso evita gastar presupuesto de consultas en datos rotos.
    """

    valor: str

    def __post_init__(self) -> None:
        limpio = re.sub(r"[\s\-.]", "", self.valor or "")
        object.__setattr__(self, "valor", limpio)

        if not limpio:
            raise ErrorValidacion("La cedula es obligatoria", campo="cedula")
        if not limpio.isdigit():
            raise ErrorValidacion("La cedula solo admite digitos", campo="cedula")
        if len(limpio) != 10:
            raise ErrorValidacion(
                f"La cedula debe tener 10 digitos (recibidos: {len(limpio)})",
                campo="cedula",
            )

        provincia = int(limpio[:2])
        if provincia not in _PROVINCIAS_VALIDAS:
            raise ErrorValidacion(f"Codigo de provincia invalido: {limpio[:2]}", campo="cedula")

        # El tercer digito distingue el tipo de persona. 6 y 7 corresponden a
        # entidades publicas y sociedades: no son personas naturales.
        if int(limpio[2]) >= 6:
            raise ErrorValidacion(
                "El tercer digito indica que no es una cedula de persona natural",
                campo="cedula",
            )

        if not self._verificar(limpio):
            raise ErrorValidacion(
                "El digito verificador de la cedula no es correcto", campo="cedula"
            )

    @staticmethod
    def _verificar(digitos: str) -> bool:
        total = 0
        for digito, coeficiente in zip(digitos[:9], _COEFICIENTES_CEDULA, strict=True):
            producto = int(digito) * coeficiente
            total += producto - 9 if producto >= 10 else producto
        verificador = (10 - total % 10) % 10
        return verificador == int(digitos[9])

    @classmethod
    def es_valida(cls, valor: str) -> bool:
        """Comprobacion sin excepciones, para filtrar lotes de importacion."""
        try:
            cls(valor)
        except ErrorValidacion:
            return False
        return True

    @property
    def provincia(self) -> int:
        return int(self.valor[:2])

    def enmascarada(self) -> str:
        """`1712345678` → `17******78`. Para logs y pantallas de bajo privilegio."""
        return f"{self.valor[:2]}{'*' * 6}{self.valor[-2:]}"

    def __str__(self) -> str:
        return self.valor


# ---------------------------------------------------------------------------
# Correo electronico
# ---------------------------------------------------------------------------

_PATRON_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email:
    """Correo normalizado a minusculas."""

    valor: str

    def __post_init__(self) -> None:
        limpio = (self.valor or "").strip().lower()
        object.__setattr__(self, "valor", limpio)

        if not limpio:
            raise ErrorValidacion("El correo es obligatorio", campo="email")
        if len(limpio) > 254:
            raise ErrorValidacion("El correo excede los 254 caracteres", campo="email")
        if not _PATRON_EMAIL.match(limpio):
            raise ErrorValidacion(f"Correo invalido: {limpio}", campo="email")

    @property
    def dominio(self) -> str:
        return self.valor.rsplit("@", 1)[1]

    @property
    def usuario(self) -> str:
        return self.valor.rsplit("@", 1)[0]

    def es_institucional(self, dominios: frozenset[str]) -> bool:
        return self.dominio in dominios

    def __str__(self) -> str:
        return self.valor


# ---------------------------------------------------------------------------
# Contrasena en claro (solo vive en memoria, nunca se persiste)
# ---------------------------------------------------------------------------

_SECUENCIAS_DEBILES = (
    "123456",
    "654321",
    "qwerty",
    "asdfgh",
    "password",
    "contrasena",
    "abcdef",
    "111111",
    "000000",
    "ute2026",
    "admin",
)


@dataclass(frozen=True, slots=True)
class ContrasenaEnClaro:
    """Contrasena antes de hashear. Valida la politica de complejidad.

    Su `__repr__` esta sobrescrito para que el valor no se filtre en trazas de
    excepcion ni en volcados de depuracion.
    """

    valor: str
    longitud_minima: int = 10

    def __post_init__(self) -> None:
        valor = self.valor or ""

        if len(valor) < self.longitud_minima:
            raise ErrorValidacion(
                f"La contrasena debe tener al menos {self.longitud_minima} caracteres",
                campo="password",
            )
        if len(valor) > 128:
            raise ErrorValidacion("La contrasena no puede exceder 128 caracteres", campo="password")

        faltantes: list[str] = []
        if not any(c.isupper() for c in valor):
            faltantes.append("una mayuscula")
        if not any(c.islower() for c in valor):
            faltantes.append("una minuscula")
        if not any(c.isdigit() for c in valor):
            faltantes.append("un digito")
        if valor.isalnum():
            faltantes.append("un caracter especial")
        if faltantes:
            raise ErrorValidacion(
                "La contrasena debe incluir " + ", ".join(faltantes), campo="password"
            )

        minuscula = valor.lower()
        if any(seq in minuscula for seq in _SECUENCIAS_DEBILES):
            raise ErrorValidacion(
                "La contrasena contiene una secuencia demasiado comun", campo="password"
            )

    def __repr__(self) -> str:
        return "ContrasenaEnClaro(***)"

    def __str__(self) -> str:
        return "***"


# ---------------------------------------------------------------------------
# Nombre de persona
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NombrePersona:
    """Nombres y apellidos, con una forma normalizada para busquedas."""

    nombres: str
    apellidos: str

    def __post_init__(self) -> None:
        nombres = " ".join((self.nombres or "").split()).title()
        apellidos = " ".join((self.apellidos or "").split()).title()

        if not nombres:
            raise ErrorValidacion("Los nombres son obligatorios", campo="nombres")
        if not apellidos:
            raise ErrorValidacion("Los apellidos son obligatorios", campo="apellidos")
        if len(nombres) > 120 or len(apellidos) > 120:
            raise ErrorValidacion(
                "Nombres y apellidos no pueden exceder 120 caracteres", campo="nombres"
            )

        object.__setattr__(self, "nombres", nombres)
        object.__setattr__(self, "apellidos", apellidos)

    @property
    def completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    @property
    def formal(self) -> str:
        """`Apellidos, Nombres` — orden usado en listados y reportes oficiales."""
        return f"{self.apellidos}, {self.nombres}"

    @property
    def normalizado(self) -> str:
        """Sin acentos y en minusculas, para indices de busqueda."""
        return normalizar_texto(self.completo)


def normalizar_texto(texto: str) -> str:
    """Minusculas, sin acentos y con espacios colapsados.

    Se usa para comparar cadenas provenientes del proveedor externo, que llegan
    con acentuacion inconsistente entre consultas: sin esta normalizacion, el
    reconciliador reportaria cambios falsos cada vez que cambia una tilde.
    """
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


# ---------------------------------------------------------------------------
# Periodo de cobertura
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PeriodoCobertura:
    """Ventana temporal durante la cual nadie se reconsulta.

    Es la pieza que garantiza la regla pedida: *no volver a consultar a una
    persona hasta que todo el padron haya sido cubierto*. Un job de cobertura
    pertenece a exactamente un periodo, y la seleccion de candidatos excluye a
    quien ya fue consultado dentro de el.
    """

    inicio: datetime
    fin: datetime

    def __post_init__(self) -> None:
        if self.inicio.tzinfo is None or self.fin.tzinfo is None:
            raise ErrorValidacion("El periodo debe usar fechas con zona horaria", campo="periodo")
        if self.inicio >= self.fin:
            raise ErrorValidacion("El inicio del periodo debe ser anterior al fin", campo="periodo")

    @classmethod
    def desde(cls, inicio: datetime, *, dias: int) -> Self:
        if dias < 1:
            raise ErrorValidacion("El periodo debe abarcar al menos un dia", campo="dias")
        return cls(inicio=inicio, fin=inicio + timedelta(days=dias))

    def contiene(self, momento: datetime) -> bool:
        return self.inicio <= momento < self.fin

    def esta_vencido(self, ahora: datetime) -> bool:
        return ahora >= self.fin

    @property
    def dias(self) -> int:
        return (self.fin - self.inicio).days

    def progreso(self, ahora: datetime) -> float:
        """Fraccion transcurrida del periodo, acotada a [0, 1].

        El planificador la usa para decidir si va adelantado o atrasado frente
        al ritmo necesario para cubrir el padron antes del vencimiento.
        """
        total = (self.fin - self.inicio).total_seconds()
        transcurrido = (ahora - self.inicio).total_seconds()
        return max(0.0, min(1.0, transcurrido / total))

    def __str__(self) -> str:
        return f"{self.inicio.date().isoformat()} → {self.fin.date().isoformat()}"


# ---------------------------------------------------------------------------
# Rango de fechas para filtros y reportes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RangoFechas:
    """Rango inclusivo usado en filtros de listados y reportes."""

    desde: date | None = None
    hasta: date | None = None

    def __post_init__(self) -> None:
        if self.desde and self.hasta and self.desde > self.hasta:
            raise ErrorValidacion(
                "La fecha inicial no puede ser posterior a la final", campo="rango"
            )

    @property
    def esta_vacio(self) -> bool:
        return self.desde is None and self.hasta is None

    def contiene(self, momento: date) -> bool:
        if self.desde and momento < self.desde:
            return False
        return not (self.hasta and momento > self.hasta)


def ahora_utc() -> datetime:
    """Instante actual con zona. Todo el dominio trabaja en UTC.

    La conversion a la hora local de Ecuador ocurre solo en los bordes: la
    interfaz y el planificador horario.
    """
    return datetime.now(UTC)
