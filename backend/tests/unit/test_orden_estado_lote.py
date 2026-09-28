"""Orden de los estados de lote/proceso en la tabla y el filtro.

El sistema academico no declara un catalogo cerrado de estados, pero si tiene
un flujo de aprobacion con un orden real (Decano, DGA, Vicerrectorado,
Canciller, Rector, Aprobado, Rechazado, Cancelado). La tabla debe mostrarlo en
ese orden y no por frecuencia, que es una coincidencia de los datos y no el
proceso.
"""

from __future__ import annotations

import pytest

from app.infrastructure.db.analitica_distributivo import _ordenar_estado_lote

pytestmark = pytest.mark.unit


def test_respeta_el_orden_del_flujo_de_aprobacion() -> None:
    # Llegan en un orden cualquiera -aqui, el inverso del flujo-.
    desordenados = ["RECHAZADO", "APROBADO", "EN REVISIÓN POR DGA", "EN REVISIÓN POR DECANO"]
    assert _ordenar_estado_lote(desordenados) == (
        "EN REVISIÓN POR DECANO",
        "EN REVISIÓN POR DGA",
        "APROBADO",
        "RECHAZADO",
    )


def test_agrega_los_desconocidos_al_final_sin_perderlos() -> None:
    """El flujo no declara todos los estados posibles; ninguno se descarta."""
    estados = ["INICIAR CONTRATACIÓN", "APROBADO", "OTRO ESTADO NUEVO", "RECHAZADO"]
    resultado = _ordenar_estado_lote(estados)

    assert set(resultado) == set(estados)
    assert resultado[:2] == ("APROBADO", "RECHAZADO")
    # Los desconocidos conservan el orden relativo con que llegaron.
    assert resultado[2:] == ("INICIAR CONTRATACIÓN", "OTRO ESTADO NUEVO")


def test_una_lista_vacia_no_falla() -> None:
    assert _ordenar_estado_lote([]) == ()


def test_solo_desconocidos_conserva_el_orden_de_llegada() -> None:
    assert _ordenar_estado_lote(["B", "A"]) == ("B", "A")
