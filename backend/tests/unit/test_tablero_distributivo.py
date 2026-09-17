"""Pruebas del tablero del distributivo.

Lo que se protege es la eleccion del periodo con el que se compara. El codigo
institucional es `AA P NN D`: dos digitos de anio, el semestre, dos que
distinguen tecnologia (15), grado (65) y posgrado (75), y uno que separa el
ordinario del interciclo. Cada semestre produce hasta seis periodos, asi que
«el anterior» de la lista casi nunca es el anterior comparable.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.casos_uso.analitica import EntradaTableroDistributivo, _elegir
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


class TestEleccionDelPeriodo:
    def test_sin_indicar_nada_toma_el_mas_reciente(self) -> None:
        actual, _ = _elegir(catalogo(), EntradaTableroDistributivo())

        assert actual.codigo == "262751"

    def test_compara_contra_el_anterior_del_mismo_tipo(self) -> None:
        """No contra el siguiente de la lista, que seria otro nivel.

        `2026-2 GRADO` frente a `2026-2 POSGRADO` no dice nada; frente a
        `2026-1 GRADO`, si.
        """
        periodos = catalogo()
        grado_2026_2 = next(p for p in periodos if p.codigo == "262651")

        actual, anterior = _elegir(periodos, EntradaTableroDistributivo(pao_id=grado_2026_2.id))

        assert actual.codigo == "262651"
        assert anterior is not None
        assert anterior.codigo == "261651"

    def test_el_interciclo_se_compara_con_otro_interciclo(self) -> None:
        periodos = [*catalogo(), periodo("251650")]
        interciclo = next(p for p in periodos if p.codigo == "261650")

        _, anterior = _elegir(periodos, EntradaTableroDistributivo(pao_id=interciclo.id))

        assert anterior is not None
        assert anterior.codigo == "251650"

    def test_sin_uno_del_mismo_tipo_cae_al_anterior_que_haya(self) -> None:
        """Mejor comparar con algo que dejar la mitad de la pantalla vacia."""
        periodos = [periodo("262651"), periodo("261751")]

        _, anterior = _elegir(periodos, EntradaTableroDistributivo(pao_id=periodos[0].id))

        assert anterior is not None
        assert anterior.codigo == "261751"

    def test_el_periodo_mas_antiguo_no_tiene_con_que_compararse(self) -> None:
        periodos = catalogo()
        el_mas_viejo = periodos[-1]

        actual, anterior = _elegir(periodos, EntradaTableroDistributivo(pao_id=el_mas_viejo.id))

        assert actual.codigo == "251651"
        assert anterior is None

    def test_respeta_los_dos_periodos_que_se_indiquen(self) -> None:
        periodos = catalogo()
        uno, otro = periodos[2], periodos[7]

        actual, anterior = _elegir(
            periodos,
            EntradaTableroDistributivo(pao_id=uno.id, pao_anterior_id=otro.id),
        )

        assert (actual.codigo, anterior and anterior.codigo) == ("262151", "251651")

    def test_un_periodo_inexistente_no_deja_la_pantalla_sin_datos(self) -> None:
        """Un id que ya no existe —un enlace guardado— cae al mas reciente."""
        actual, _ = _elegir(catalogo(), EntradaTableroDistributivo(pao_id=uuid4()))

        assert actual.codigo == "262751"
