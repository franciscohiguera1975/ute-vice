"""Captura de la asignatura que imparte cada docente.

Es el unico dato del reporte institucional que no existe en el consolidado —el
distributivo reparte horas por tipo de actividad, no por materia— asi que se
captura a mano sobre cientos de filas. De ahi que se guarde por tandas.

La pantalla manda **texto** y el caso de uso lo resuelve contra el catalogo,
creando el elemento si no existe: obligar a elegir de una lista que empieza
vacia no seria capturar nada.

Una fila admite **varias** materias, separadas por comas: es el mismo signo con
que salen despues en la celda del reporte.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from tests.conftest import hacer_usuario

from app.application.base import ContextoEjecucion
from app.application.casos_uso.distributivo import AsignaturaDeFila, CapturarAsignaturas
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import FilaDistributivo
from app.domain.enums import RolCodigo
from app.domain.errors import ErrorValidacion, NoEncontrado

pytestmark = pytest.mark.unit


@pytest.fixture
def contexto_admin(roles):  # type: ignore[no-untyped-def]
    return ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )


def _nombres_asignaturas(uow, fila_id):  # type: ignore[no-untyped-def]
    """Los textos de las asignaturas enlazadas, en orden."""
    catalogo = uow.catalogos.datos[TipoCatalogo.ASIGNATURA]
    return [catalogo[i].nombre for i in uow.distributivo.datos[fila_id].asignaturas_ids]


def _con_asignatura(uow, texto):  # type: ignore[no-untyped-def]
    """Siembra un elemento del catalogo y devuelve su identificador."""
    elemento = ElementoCatalogo(tipo=TipoCatalogo.ASIGNATURA, codigo=texto.upper(), nombre=texto)
    uow.catalogos.datos[TipoCatalogo.ASIGNATURA][elemento.id] = elemento
    return elemento.id


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
    assert _nombres_asignaturas(uow, a.id) == ["CALCULO I"]
    assert _nombres_asignaturas(uow, b.id) == ["FISICA"]
    assert uow.commits == 1

    # Ninguna de las dos existia: el catalogo se poblo solo.
    assert resultado.asignaturas_creadas == 2


async def test_no_toca_lo_que_no_cambia(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """El texto resuelve al mismo elemento: no hay nada que guardar."""
    asignatura_id = _con_asignatura(uow, "CALCULO I")
    fila = _fila(uow, asignaturas_ids=[asignatura_id])

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="  CALCULO   I ")],
        contexto_admin,
    )

    assert resultado.actualizadas == 0
    assert resultado.sin_cambios == 1
    assert resultado.asignaturas_creadas == 0


async def test_dos_grafias_del_mismo_nombre_son_una_sola(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Es la razon de ser del catalogo: una materia, una entrada."""
    a, b = _fila(uow), _fila(uow)

    resultado = await CapturarAsignaturas(uow)(
        [
            AsignaturaDeFila(fila_id=a.id, asignatura="Calculo I"),
            AsignaturaDeFila(fila_id=b.id, asignatura="  CALCULO   I  "),
        ],
        contexto_admin,
    )

    assert resultado.actualizadas == 2
    assert resultado.asignaturas_creadas == 1
    assert (
        uow.distributivo.datos[a.id].asignaturas_ids == uow.distributivo.datos[b.id].asignaturas_ids
    )
    assert len(uow.catalogos.datos[TipoCatalogo.ASIGNATURA]) == 1


async def test_reutiliza_lo_que_ya_esta_en_el_catalogo(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    existente = _con_asignatura(uow, "Anatomia Humana")
    fila = _fila(uow)

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="anatomia humana")],
        contexto_admin,
    )

    assert resultado.asignaturas_creadas == 0
    assert uow.distributivo.datos[fila.id].asignaturas_ids == [existente]


async def test_texto_vacio_retira_las_asignaturas(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Retira los enlaces, sin borrar la asignatura del catalogo."""
    asignatura_id = _con_asignatura(uow, "CALCULO I")
    fila = _fila(uow, asignaturas_ids=[asignatura_id])

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="")],
        contexto_admin,
    )

    assert resultado.actualizadas == 1
    assert uow.distributivo.datos[fila.id].asignaturas_ids == []
    assert len(uow.catalogos.datos[TipoCatalogo.ASIGNATURA]) == 1


async def test_una_fila_admite_varias_materias_separadas_por_comas(  # type: ignore[no-untyped-def]
    uow, contexto_admin
) -> None:
    """Es el mismo signo con que salen despues en la celda del reporte."""
    fila = _fila(uow)

    resultado = await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="Calculo I, Algebra Lineal, Fisica")],
        contexto_admin,
    )

    assert resultado.actualizadas == 1
    assert resultado.asignaturas_creadas == 3
    assert _nombres_asignaturas(uow, fila.id) == ["Calculo I", "Algebra Lineal", "Fisica"]


async def test_la_misma_materia_repetida_en_el_texto_entra_una_vez(  # type: ignore[no-untyped-def]
    uow, contexto_admin
) -> None:
    fila = _fila(uow)

    await CapturarAsignaturas(uow)(
        [AsignaturaDeFila(fila_id=fila.id, asignatura="Calculo I, CALCULO   I, Fisica")],
        contexto_admin,
    )

    assert _nombres_asignaturas(uow, fila.id) == ["Calculo I", "Fisica"]


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


class TestCodigoErp:
    """El codigo del elemento en el ERP academico."""

    def test_se_normaliza_a_mayusculas_y_sin_espacios(self) -> None:
        elemento = ElementoCatalogo(
            tipo=TipoCatalogo.FACULTAD, codigo="FCSEE", nombre="Salud", codigo_erp=" fs "
        )
        assert elemento.codigo_erp == "FS"

    def test_por_omision_esta_vacio(self) -> None:
        elemento = ElementoCatalogo(tipo=TipoCatalogo.FACULTAD, codigo="FO", nombre="Odonto")
        assert elemento.codigo_erp == ""

    def test_no_es_unico_dos_elementos_pueden_compartirlo(self) -> None:
        # `FCSEE` y `PFCSEE` son dos unidades aqui y una sola —`FS`— en el ERP.
        uno = ElementoCatalogo(
            tipo=TipoCatalogo.FACULTAD, codigo="FCSEE", nombre="Salud", codigo_erp="FS"
        )
        otro = ElementoCatalogo(
            tipo=TipoCatalogo.FACULTAD, codigo="PFCSEE", nombre="Posgrados", codigo_erp="FS"
        )
        assert uno.codigo_erp == otro.codigo_erp
        assert uno != otro

    def test_se_puede_actualizar_aunque_el_codigo_no(self) -> None:
        elemento = ElementoCatalogo(tipo=TipoCatalogo.FACULTAD, codigo="FAU", nombre="Arqui")
        elemento.actualizar(codigo_erp="fu")

        assert elemento.codigo_erp == "FU"
        assert elemento.codigo == "FAU"

    def test_rechaza_uno_demasiado_largo(self) -> None:
        with pytest.raises(ErrorValidacion):
            ElementoCatalogo(
                tipo=TipoCatalogo.FACULTAD, codigo="FO", nombre="Odonto", codigo_erp="X" * 65
            )
