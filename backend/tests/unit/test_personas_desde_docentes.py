"""Alta de personas a partir del padron docente."""

from __future__ import annotations

import pytest
from tests.conftest import CEDULAS_VALIDAS, hacer_usuario

from app.application.base import ContextoEjecucion
from app.application.casos_uso.personas_desde_docentes import (
    SincronizarPersonasDesdeDocentes,
    separar_nombre,
)
from app.domain.entities.distributivo import Docente
from app.domain.enums import RolCodigo, TipoVinculacion
from app.domain.errors import ErrorValidacion
from app.domain.value_objects_distributivo import Identificacion

pytestmark = pytest.mark.unit


@pytest.fixture
def contexto_admin(roles):  # type: ignore[no-untyped-def]
    return ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )


# ===========================================================================
# Separacion del nombre
# ===========================================================================


@pytest.mark.parametrize(
    ("completo", "apellidos", "nombres"),
    [
        # Lo habitual en el padron: dos apellidos y dos nombres.
        ("ABARCA ACHIG MARITZA CATALINA", "Abarca Achig", "Maritza Catalina"),
        # Tres palabras: se asume un solo nombre.
        ("PEREZ GOMEZ LUIS", "Perez Gomez", "Luis"),
        # Dos: un apellido y un nombre.
        ("PEREZ LUIS", "Perez", "Luis"),
        # Cinco o mas: todo lo que sobra son nombres.
        ("DE LA TORRE RUIZ ANA MARIA", "De La", "Torre Ruiz Ana Maria"),
    ],
)
def test_separa_apellidos_de_nombres(completo, apellidos, nombres) -> None:  # type: ignore[no-untyped-def]
    nombre = separar_nombre(completo)
    assert nombre.apellidos == apellidos
    assert nombre.nombres == nombres


def test_un_nombre_de_una_sola_palabra_no_se_puede_separar() -> None:
    """No hay forma de acertar: se informa en lugar de inventar un apellido."""
    with pytest.raises(ErrorValidacion, match="separar"):
        separar_nombre("PEREZ")


# ===========================================================================
# La sincronizacion
# ===========================================================================


def _docente(uow, identificacion, nombre="PEREZ GOMEZ LUIS ALBERTO", **cambios):  # type: ignore[no-untyped-def]
    docente = Docente(
        identificacion=Identificacion(identificacion), nombre_completo=nombre, **cambios
    )
    uow.docentes.datos[docente.id] = docente
    return docente


async def test_crea_una_persona_por_docente(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    _docente(uow, CEDULAS_VALIDAS[0])
    _docente(uow, CEDULAS_VALIDAS[1], nombre="LOPEZ DIAZ ANA MARIA")

    resultado = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)

    assert resultado.personas_creadas == 2
    assert len(uow.personas.datos) == 2
    assert all(d.persona_id is not None for d in uow.docentes.datos.values())
    assert all(p.tipo_vinculacion is TipoVinculacion.DOCENTE for p in uow.personas.datos.values())


async def test_es_idempotente(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Correrlo dos veces no duplica a nadie."""
    _docente(uow, CEDULAS_VALIDAS[0])

    primera = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)
    segunda = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)

    assert primera.personas_creadas == 1
    assert segunda.personas_creadas == 0
    assert segunda.ya_estaban == 1
    assert len(uow.personas.datos) == 1


async def test_los_docentes_con_pasaporte_quedan_fuera(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """`Persona` exige cedula: es con lo que se consulta al registro nacional."""
    _docente(uow, CEDULAS_VALIDAS[0])
    _docente(uow, "AB123456", nombre="SMITH JONES JOHN")

    resultado = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)

    assert resultado.personas_creadas == 1
    assert resultado.sin_cedula == 1
    assert len(uow.personas.datos) == 1


async def test_enlaza_en_lugar_de_duplicar_si_la_persona_ya_existe(  # type: ignore[no-untyped-def]
    uow, contexto_admin
) -> None:
    """El padron de personas puede venir de otra carga anterior."""
    from tests.conftest import hacer_persona

    persona = hacer_persona(cedula=CEDULAS_VALIDAS[0])
    uow.personas.datos[persona.id] = persona
    docente = _docente(uow, CEDULAS_VALIDAS[0])

    resultado = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)

    assert resultado.personas_creadas == 0
    assert resultado.docentes_enlazados == 1
    assert uow.docentes.datos[docente.id].persona_id == persona.id
    assert len(uow.personas.datos) == 1


async def test_un_nombre_irreducible_se_informa_y_no_detiene_al_resto(  # type: ignore[no-untyped-def]
    uow, contexto_admin
) -> None:
    _docente(uow, CEDULAS_VALIDAS[0], nombre="CHERREZ")
    _docente(uow, CEDULAS_VALIDAS[1], nombre="LOPEZ DIAZ ANA MARIA")

    resultado = await SincronizarPersonasDesdeDocentes(uow)(None, contexto_admin)

    assert resultado.personas_creadas == 1
    assert len(resultado.problemas) == 1
    assert CEDULAS_VALIDAS[0] in resultado.problemas[0]
