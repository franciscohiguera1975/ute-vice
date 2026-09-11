"""Alcance academico de un usuario.

Quien coordina una facultad no tiene por que ver el distributivo de las otras.
El alcance acota lo que una cuenta puede consultar a un conjunto de facultades
y de carreras.

**Un alcance vacio no restringe nada.** Es deliberado: el permiso ya decide si
alguien puede entrar a una pantalla, y el alcance solo acota *cuanto* ve dentro
de ella. Si vaciarlo significara «no ve nada», cualquier cuenta a la que se
olvidara asignarle facultades quedaria mirando una pantalla en blanco sin
explicacion, y el sistema entero habria cambiado de comportamiento al agregar
esta funcion.

Facultades y carreras se suman, no se cruzan: quien tiene la facultad FCID y
ademas la carrera «Medicina» ve **todo** FCID **y ademas** Medicina, aunque
Medicina pertenezca a otra facultad. Cruzarlas obligaria a repetir la carrera
de cada facultad para conceder lo mismo.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AlcanceAcademico:
    """Que facultades y carreras puede consultar una cuenta."""

    facultades: frozenset[UUID] = field(default_factory=frozenset)
    carreras: frozenset[UUID] = field(default_factory=frozenset)

    @classmethod
    def total(cls) -> AlcanceAcademico:
        """Sin restriccion. Lo que tienen los administradores."""
        return cls()

    @classmethod
    def de(
        cls,
        facultades: Iterable[UUID] = (),
        carreras: Iterable[UUID] = (),
    ) -> AlcanceAcademico:
        """Construye desde cualquier iterable, sin exigir conjuntos."""
        return cls(facultades=frozenset(facultades), carreras=frozenset(carreras))

    @property
    def es_total(self) -> bool:
        """`True` si no acota nada."""
        return not self.facultades and not self.carreras

    def permite(self, *, facultad_id: UUID | None, carrera_id: UUID | None) -> bool:
        """`True` si una fila con esa facultad y esa carrera entra en el alcance."""
        if self.es_total:
            return True
        return (facultad_id is not None and facultad_id in self.facultades) or (
            carrera_id is not None and carrera_id in self.carreras
        )

    def unir(self, otro: AlcanceAcademico) -> AlcanceAcademico:
        """Suma de dos alcances. Si alguno es total, el resultado es total."""
        if self.es_total or otro.es_total:
            return AlcanceAcademico.total()
        return AlcanceAcademico(
            facultades=self.facultades | otro.facultades,
            carreras=self.carreras | otro.carreras,
        )

    def __str__(self) -> str:
        if self.es_total:
            return "sin restriccion"
        return f"{len(self.facultades)} facultad(es), {len(self.carreras)} carrera(s)"
