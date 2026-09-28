"""Orden de los estados de lote/proceso en la tabla y el filtro.

El sistema academico no declara un catalogo cerrado de estados, pero cada uno
de los tres flujos de aprobacion (`TipoFlujoContrato`) si tiene un orden real
de pasos. La tabla debe mostrarlo en ese orden y no por frecuencia, que es una
coincidencia de los datos y no del proceso.
"""

from __future__ import annotations

import pytest

from app.domain.enums import TipoFlujoContrato
from app.infrastructure.db.analitica_distributivo import _ordenar_estado_lote

pytestmark = pytest.mark.unit

_ORDEN_NORMAL = TipoFlujoContrato.NORMAL.orden_estados


def test_respeta_el_orden_del_flujo_de_aprobacion() -> None:
    # Llegan en un orden cualquiera -aqui, el inverso del flujo-.
    desordenados = ["RECHAZADO", "APROBADO", "EN REVISIÓN POR DGA", "EN REVISIÓN POR DECANO"]
    assert _ordenar_estado_lote(desordenados, _ORDEN_NORMAL) == (
        "EN REVISIÓN POR DECANO",
        "EN REVISIÓN POR DGA",
        "APROBADO",
        "RECHAZADO",
    )


def test_agrega_los_desconocidos_al_final_sin_perderlos() -> None:
    """El flujo no declara todos los estados posibles; ninguno se descarta."""
    estados = ["INICIAR CONTRATACIÓN", "APROBADO", "OTRO ESTADO NUEVO", "RECHAZADO"]
    resultado = _ordenar_estado_lote(estados, _ORDEN_NORMAL)

    assert set(resultado) == set(estados)
    assert resultado[:2] == ("APROBADO", "RECHAZADO")
    # Los desconocidos conservan el orden relativo con que llegaron.
    assert resultado[2:] == ("INICIAR CONTRATACIÓN", "OTRO ESTADO NUEVO")


def test_una_lista_vacia_no_falla() -> None:
    assert _ordenar_estado_lote([], _ORDEN_NORMAL) == ()


def test_solo_desconocidos_conserva_el_orden_de_llegada() -> None:
    assert _ordenar_estado_lote(["B", "A"], _ORDEN_NORMAL) == ("B", "A")


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
