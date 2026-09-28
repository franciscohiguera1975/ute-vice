"""Orden de los estados de lote/proceso en la tabla y el filtro.

El sistema academico no declara un catalogo cerrado de estados, pero cada uno
de los tres flujos de aprobacion (`TipoFlujoContrato`) si tiene un orden real
de pasos, y esos pasos deben verse completos aunque alguno no tenga todavia
ninguna fila -«En revision por Canciller» antes de que alguien llegue ahi-,
no solo los que ya ocurrieron.
"""

from __future__ import annotations

import pytest

from app.domain.enums import TipoFlujoContrato
from app.infrastructure.db.analitica_distributivo import _ordenar_estado_lote

pytestmark = pytest.mark.unit

_ORDEN_NORMAL = TipoFlujoContrato.NORMAL.orden_estados


def test_el_flujo_sale_completo_aunque_falten_pasos_en_los_datos() -> None:
    # Ni "Vicerrectorado" ni "Cancelado" aparecen en los datos...
    estados = ["RECHAZADO", "APROBADO", "EN REVISIÓN POR DGA", "EN REVISIÓN POR DECANO"]
    # ...pero igual salen, porque son pasos del flujo.
    assert _ordenar_estado_lote(estados, _ORDEN_NORMAL) == _ORDEN_NORMAL


def test_agrega_los_desconocidos_al_final_sin_perderlos() -> None:
    """El flujo no declara todos los estados posibles; ninguno se descarta."""
    estados = ["INICIAR CONTRATACIÓN", "APROBADO", "OTRO ESTADO NUEVO", "RECHAZADO"]
    resultado = _ordenar_estado_lote(estados, _ORDEN_NORMAL)

    # El flujo completo primero...
    assert resultado[: len(_ORDEN_NORMAL)] == _ORDEN_NORMAL
    # ...los desconocidos despues, en el orden con que llegaron.
    assert resultado[len(_ORDEN_NORMAL) :] == ("INICIAR CONTRATACIÓN", "OTRO ESTADO NUEVO")


def test_sin_datos_todavia_sale_el_flujo_completo() -> None:
    """Nada impide mostrar los pasos: son del flujo, no de los datos."""
    assert _ordenar_estado_lote([], _ORDEN_NORMAL) == _ORDEN_NORMAL


def test_solo_desconocidos_van_despues_del_flujo_completo() -> None:
    resultado = _ordenar_estado_lote(["B", "A"], _ORDEN_NORMAL)
    assert resultado == (*_ORDEN_NORMAL, "B", "A")


class TestOrdenPorFlujo:
    """Cada flujo tiene su propio orden de pasos: no son intercambiables."""

    def test_el_normal_no_incluye_canciller_ni_rector(self) -> None:
        assert "EN REVISIÓN POR CANCILLER" not in TipoFlujoContrato.NORMAL.orden_estados
        assert "EN REVISIÓN POR RECTOR" not in TipoFlujoContrato.NORMAL.orden_estados

    def test_la_contratacion_pasa_por_canciller_y_rector(self) -> None:
        orden = TipoFlujoContrato.CONTRATACION.orden_estados
        assert orden.index("EN REVISIÓN POR VICERRECTORADO") < orden.index(
            "EN REVISIÓN POR CANCILLER"
        )
        assert orden.index("EN REVISIÓN POR CANCILLER") < orden.index("EN REVISIÓN POR RECTOR")

    def test_el_simplificado_solo_pide_al_decano(self) -> None:
        assert TipoFlujoContrato.SIMPLIFICADO.orden_estados == (
            "EN REVISIÓN POR DECANO",
            "APROBADO",
            "RECHAZADO",
            "CANCELADO",
        )

    def test_los_tres_terminan_igual(self) -> None:
        """Aprobado, Rechazado y Cancelado cierran cualquiera de los flujos."""
        cierre = ("APROBADO", "RECHAZADO", "CANCELADO")
        for tipo in TipoFlujoContrato:
            assert tipo.orden_estados[-3:] == cierre
