"""Pruebas de la eleccion de los dos grupos que se comparan.

La usan las dos pantallas —el tablero y los resumenes— y por eso vive en un
solo sitio: si una propusiera «2026-2 POSGRADO» y la otra «2026-2 completo»,
sus cifras no cuadrarian y nadie sabria cual creer.

Un semestre son varios periodos. El codigo institucional es `AA P NN D`: dos
digitos de anio, el semestre, dos que distinguen tecnologia (15), grado (65) y
posgrado (75), y uno que separa el ordinario del interciclo. Comparar un
periodo suelto con el siguiente de la lista casi nunca compara lo mismo.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.casos_uso.analitica import EntradaResumenComparativo, _grupos
from app.domain.ports.analitica import PeriodoDisponible

pytestmark = pytest.mark.unit


def periodo(codigo: str, filas: int = 100) -> PeriodoDisponible:
    return PeriodoDisponible(
        id=uuid4(), codigo=codigo, nombre=f"Periodo {codigo}", semestre="", filas=filas
    )


#: De mas nuevo a mas viejo, como los devuelve el repositorio.
def catalogo() -> list[PeriodoDisponible]:
    return [
        periodo("262751"),  # 2026-2 posgrado
        periodo("262651"),  # 2026-2 grado
        periodo("262151"),  # 2026-2 tecnologia
        periodo("261750"),  # 2026-1 posgrado interciclo
        periodo("261751"),  # 2026-1 posgrado
        periodo("261650"),  # 2026-1 grado interciclo
        periodo("261651"),  # 2026-1 grado
        periodo("251651"),  # 2025-1 grado
    ]


class TestGruposPorDefecto:
    """Que dos grupos se comparan cuando no se indica ninguno.

    Un semestre son varios periodos: `2026-1` es tecnologia, grado y posgrado,
    mas sus interciclos. La propuesta por defecto tiene que ser el semestre
    entero, no un periodo suelto — si no, «26-1 contra 26-2» obligaria a marcar
    seis casillas para ver lo que se pide siempre.
    """

    @staticmethod
    def _con_semestre(codigo: str, semestre: str) -> PeriodoDisponible:
        return PeriodoDisponible(
            id=uuid4(), codigo=codigo, nombre=codigo, semestre=semestre, filas=10
        )

    def _catalogo(self) -> list[PeriodoDisponible]:
        return [
            self._con_semestre("262751", "2026-2"),
            self._con_semestre("262651", "2026-2"),
            self._con_semestre("262151", "2026-2"),
            self._con_semestre("261751", "2026-1"),
            self._con_semestre("261650", "2026-1"),
            self._con_semestre("261651", "2026-1"),
            self._con_semestre("252651", "2025-2"),
        ]

    def test_toma_los_dos_ultimos_semestres_enteros(self) -> None:
        periodos = self._catalogo()
        a, b = _grupos(periodos, EntradaResumenComparativo())

        codigos = {p.id: p.codigo for p in periodos}
        assert sorted(codigos[i] for i in a) == ["261650", "261651", "261751"]
        assert sorted(codigos[i] for i in b) == ["262151", "262651", "262751"]

    def test_el_interciclo_entra_en_su_semestre(self) -> None:
        periodos = self._catalogo()
        a, _ = _grupos(periodos, EntradaResumenComparativo())
        codigos = {p.id: p.codigo for p in periodos}

        assert "261650" in {codigos[i] for i in a}

    def test_respeta_los_grupos_que_se_indiquen(self) -> None:
        periodos = self._catalogo()
        elegido = periodos[6].id

        a, b = _grupos(periodos, EntradaResumenComparativo(grupo_a=(elegido,)))

        assert a == [elegido]
        assert b == []

    def test_descarta_periodos_que_ya_no_existen(self) -> None:
        """Un enlace guardado con un periodo borrado no debe romper la pantalla."""
        periodos = self._catalogo()
        vivo = periodos[0].id

        a, _ = _grupos(periodos, EntradaResumenComparativo(grupo_a=(vivo, uuid4())))

        assert a == [vivo]

    def test_con_un_solo_semestre_ese_es_el_actual_y_no_hay_referencia(self) -> None:
        """Al reves, el avance saldria 0 % y diria que no se planifico nada."""
        periodos = [self._con_semestre("262651", "2026-2")]

        a, b = _grupos(periodos, EntradaResumenComparativo())

        assert a == []
        assert len(b) == 1
