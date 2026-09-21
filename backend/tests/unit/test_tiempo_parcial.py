"""Pruebas de la eleccion del grupo para la pantalla de tiempo parcial.

Es la version de un solo grupo de `_grupos` (ver `test_tablero_distributivo.py`):
la misma idea de proponer el semestre entero por defecto, pero para una
pantalla que examina un solo PAO y no compara dos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.casos_uso.analitica import _grupo_unico
from app.domain.ports.analitica import PeriodoDisponible

pytestmark = pytest.mark.unit


def _con_semestre(codigo: str, semestre: str) -> PeriodoDisponible:
    return PeriodoDisponible(id=uuid4(), codigo=codigo, nombre=codigo, semestre=semestre, filas=10)


def _catalogo() -> list[PeriodoDisponible]:
    return [
        _con_semestre("262751", "2026-2"),
        _con_semestre("262651", "2026-2"),
        _con_semestre("262151", "2026-2"),
        _con_semestre("261751", "2026-1"),
        _con_semestre("261650", "2026-1"),
        _con_semestre("261651", "2026-1"),
    ]


class TestGrupoPorDefecto:
    def test_toma_el_semestre_mas_reciente_completo(self) -> None:
        periodos = _catalogo()
        grupo = _grupo_unico(periodos, ())

        codigos = {p.id: p.codigo for p in periodos}
        assert sorted(codigos[i] for i in grupo) == ["262151", "262651", "262751"]

    def test_el_interciclo_entra_en_su_semestre(self) -> None:
        periodos = _catalogo()
        grupo = _grupo_unico(periodos, ())
        codigos = {p.id: p.codigo for p in periodos}

        # El interciclo de 2026-1 no deberia aparecer: el mas reciente es 2026-2.
        assert "261650" not in {codigos[i] for i in grupo}

    def test_respeta_lo_que_se_elija(self) -> None:
        periodos = _catalogo()
        elegido = periodos[3].id

        grupo = _grupo_unico(periodos, (elegido,))

        assert grupo == [elegido]

    def test_descarta_periodos_que_ya_no_existen(self) -> None:
        periodos = _catalogo()
        vivo = periodos[0].id

        grupo = _grupo_unico(periodos, (vivo, uuid4()))

        assert grupo == [vivo]
