"""Captura de la asignatura que imparte cada docente.

Es el unico dato del reporte institucional que no existe en el consolidado —el
distributivo reparte horas por tipo de actividad, no por materia— asi que se
captura a mano sobre cientos de filas. De ahi que se guarde por tandas.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from tests.conftest import hacer_usuario

from app.application.base import ContextoEjecucion
from app.application.casos_uso.distributivo import AsignaturaDeFila, CapturarAsignaturas
from app.domain.entities.distributivo import FilaDistributivo
from app.domain.enums import RolCodigo
from app.domain.errors import ErrorValidacion, NoEncontrado

pytestmark = pytest.mark.unit


@pytest.fixture
def contexto_admin(roles):  # type: ignore[no-untyped-def]
    return ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )


def _fila(uow, **cambios):  # type: ignore[no-untyped-def]
    base = {
        "docente_id": uuid4(),
        "pao_id": uuid4(),
        "facultad_id": uuid4(),
        "carrera_id": uuid4(),
    }
    fila = FilaDistributivo(**{**base, **cambios})
    uow.distributivo.datos[fila.id] = fila
    return fila


async def test_guarda_la_tanda_completa(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    a = _fila(uow)
    b = _fila(uow)

    resultado = await CapturarAsignaturas(uow)(
        [
            AsignaturaDeFila(fila_id=a.id, asignatura="CALCULO I"),
            AsignaturaDeFila(fila_id=b.id, asignatura="FISICA"),
        ],
        contexto_admin,
    )

    assert resultado.actualizadas == 2
    assert uow.distributivo.datos[a.id].asignatura == "CALCULO I"
    assert uow.distributivo.datos[b.id].asignatura == "FISICA"
    assert uow.commits == 1


async def test_no_toca_lo_que_no_cambia(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """El texto normaliza al mismo valor: no hay nada que guardar."""
    fila = _fila(uow, asignatura="CALCULO I")

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="  CALCULO   I ")],
        contexto_admin,
    )

    assert resultado.actualizadas == 0
    assert resultado.sin_cambios == 1


async def test_texto_vacio_borra_la_asignatura(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    fila = _fila(uow, asignatura="CALCULO I")

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="")],
        contexto_admin,
    )

    assert resultado.actualizadas == 1
    assert uow.distributivo.datos[fila.id].asignatura is None


async def test_aborta_entera_si_una_fila_no_existe(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Guardar el resto dejaria al usuario sin saber que quedo afuera."""
    fila = _fila(uow)

    with pytest.raises(NoEncontrado):
        await CapturarAsignaturas(uow)(
            [
                AsignaturaDeFila(fila_id=fila.id, asignatura="CALCULO I"),
                AsignaturaDeFila(fila_id=uuid4(), asignatura="FISICA"),
            ],
            contexto_admin,
        )

    assert uow.commits == 0


async def test_rechaza_una_tanda_vacia(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ErrorValidacion):
        await CapturarAsignaturas(uow)([], contexto_admin)


async def test_tiene_tope_por_peticion(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Es una pantalla de captura, no una importacion."""
    exceso = [
        AsignaturaDeFila(fila_id=uuid4(), asignatura="X")
        for _ in range(CapturarAsignaturas.MAXIMO + 1)
    ]
    with pytest.raises(ErrorValidacion):
        await CapturarAsignaturas(uow)(exceso, contexto_admin)
