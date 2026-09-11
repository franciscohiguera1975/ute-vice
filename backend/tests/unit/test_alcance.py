"""Alcance academico: que facultades y carreras ve cada cuenta.

Lo que importa verificar aqui es que el recorte lo impone el sistema a partir
del actor y no la peticion, y que llegar por identificador no lo esquiva.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from tests.conftest import hacer_usuario

from app.application.base import ContextoEjecucion
from app.domain.alcance import AlcanceAcademico
from app.domain.enums import RolCodigo

pytestmark = pytest.mark.unit

FCID, FCSEE = uuid4(), uuid4()
SOFTWARE, MEDICINA = uuid4(), uuid4()


# ===========================================================================
# El objeto de valor
# ===========================================================================


def test_un_alcance_vacio_no_restringe_nada() -> None:
    """Es la decision central: vaciarlo no deja a nadie sin ver."""
    alcance = AlcanceAcademico()
    assert alcance.es_total
    assert alcance.permite(facultad_id=FCID, carrera_id=SOFTWARE)


def test_permite_por_facultad() -> None:
    alcance = AlcanceAcademico.de(facultades=[FCID])
    assert alcance.permite(facultad_id=FCID, carrera_id=uuid4())
    assert not alcance.permite(facultad_id=FCSEE, carrera_id=uuid4())


def test_facultades_y_carreras_se_suman_no_se_cruzan() -> None:
    """Con FCID y Medicina se ve todo FCID **y ademas** Medicina."""
    alcance = AlcanceAcademico.de(facultades=[FCID], carreras=[MEDICINA])

    assert alcance.permite(facultad_id=FCID, carrera_id=SOFTWARE)
    assert alcance.permite(facultad_id=FCSEE, carrera_id=MEDICINA)
    assert not alcance.permite(facultad_id=FCSEE, carrera_id=SOFTWARE)


def test_una_fila_sin_facultad_ni_carrera_queda_fuera() -> None:
    alcance = AlcanceAcademico.de(facultades=[FCID])
    assert not alcance.permite(facultad_id=None, carrera_id=None)


def test_unir_con_un_alcance_total_da_total() -> None:
    acotado = AlcanceAcademico.de(facultades=[FCID])
    assert acotado.unir(AlcanceAcademico.total()).es_total
    assert AlcanceAcademico.total().unir(acotado).es_total


def test_unir_dos_acotados_suma_los_conjuntos() -> None:
    union = AlcanceAcademico.de(facultades=[FCID]).unir(AlcanceAcademico.de(carreras=[MEDICINA]))
    assert union.facultades == {FCID}
    assert union.carreras == {MEDICINA}


# ===========================================================================
# El usuario
# ===========================================================================


def test_el_superusuario_nunca_se_acota(roles) -> None:  # type: ignore[no-untyped-def]
    """Es la cuenta de rescate: acotarla podria impedir arreglar el sistema."""
    usuario = hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    usuario.facultades_ids = {FCID}

    assert usuario.alcance.es_total


def test_un_usuario_normal_lleva_su_alcance(roles) -> None:  # type: ignore[no-untyped-def]
    usuario = hacer_usuario(roles={roles[RolCodigo.CONSULTA.value]})
    usuario.definir_alcance([FCID], [MEDICINA])

    assert not usuario.alcance.es_total
    assert usuario.alcance.facultades == {FCID}
    assert usuario.alcance.carreras == {MEDICINA}


def test_definir_alcance_con_listas_vacias_lo_borra(roles) -> None:  # type: ignore[no-untyped-def]
    usuario = hacer_usuario(roles={roles[RolCodigo.CONSULTA.value]})
    usuario.definir_alcance([FCID], [MEDICINA])
    usuario.definir_alcance([], [])

    assert usuario.alcance.es_total


def test_definir_alcance_con_none_deja_esa_parte_como_estaba(roles) -> None:  # type: ignore[no-untyped-def]
    usuario = hacer_usuario(roles={roles[RolCodigo.CONSULTA.value]})
    usuario.definir_alcance([FCID], [MEDICINA])
    usuario.definir_alcance(carreras_ids=[])

    assert usuario.alcance.facultades == {FCID}
    assert usuario.alcance.carreras == set()


# ===========================================================================
# El contexto de ejecucion
# ===========================================================================


def test_sin_actor_no_hay_restriccion() -> None:
    """Las tareas automaticas no se acotan: ya vienen autorizadas."""
    assert ContextoEjecucion.sistema().alcance.es_total
    assert ContextoEjecucion().alcance.es_total


def test_el_contexto_toma_el_alcance_del_actor(roles) -> None:  # type: ignore[no-untyped-def]
    usuario = hacer_usuario(roles={roles[RolCodigo.CONSULTA.value]})
    usuario.definir_alcance([FCSEE], [])

    assert ContextoEjecucion(actor=usuario).alcance.facultades == {FCSEE}


# ===========================================================================
# Que se imponga de verdad
# ===========================================================================


@pytest.fixture
def contexto_acotado(roles):  # type: ignore[no-untyped-def]
    usuario = hacer_usuario(roles={roles[RolCodigo.COORDINADOR.value]})
    usuario.definir_alcance([FCID], [])
    return ContextoEjecucion(actor=usuario)


def _fila(uow, facultad_id=FCID, carrera_id=SOFTWARE):  # type: ignore[no-untyped-def]
    from app.domain.entities.distributivo import FilaDistributivo

    fila = FilaDistributivo(
        docente_id=uuid4(),
        pao_id=uuid4(),
        facultad_id=facultad_id,
        carrera_id=carrera_id,
    )
    uow.distributivo.datos[fila.id] = fila
    return fila


async def test_listar_impone_el_alcance_sobre_lo_que_pida_la_peticion(  # type: ignore[no-untyped-def]
    uow, contexto_acotado
) -> None:
    """Aunque la peticion no lo pida, el filtro sale con el recorte puesto."""
    from app.application.casos_uso.distributivo import (
        EntradaListarDistributivo,
        ListarDistributivo,
    )
    from app.domain.ports.distributivo import FiltroDistributivo

    await ListarDistributivo(uow)(
        EntradaListarDistributivo(filtro=FiltroDistributivo()), contexto_acotado
    )

    assert uow.distributivo.ultimo_filtro.alcance.facultades == {FCID}


async def test_el_resumen_tambien_se_acota(uow, contexto_acotado) -> None:  # type: ignore[no-untyped-def]
    from app.application.casos_uso.distributivo import ResumenDelDistributivo
    from app.domain.ports.distributivo import FiltroDistributivo

    await ResumenDelDistributivo(uow)(FiltroDistributivo(), contexto_acotado)

    assert uow.distributivo.ultimo_filtro.alcance.facultades == {FCID}


async def test_llegar_por_identificador_no_esquiva_el_alcance(  # type: ignore[no-untyped-def]
    uow, contexto_acotado
) -> None:
    """El listado ya viene recortado, pero el `id` lo rodearia."""
    from app.application.casos_uso.distributivo import ObtenerFilaDistributivo
    from app.domain.errors import FueraDeAlcance

    ajena = _fila(uow, facultad_id=FCSEE, carrera_id=MEDICINA)

    with pytest.raises(FueraDeAlcance):
        await ObtenerFilaDistributivo(uow)(ajena.id, contexto_acotado)


async def test_la_propia_facultad_si_se_puede_consultar(uow, contexto_acotado) -> None:  # type: ignore[no-untyped-def]
    from app.application.casos_uso.distributivo import ObtenerFilaDistributivo

    propia = _fila(uow)
    resuelta = await ObtenerFilaDistributivo(uow)(propia.id, contexto_acotado)

    assert resuelta.fila.id == propia.id


async def test_no_se_puede_eliminar_una_fila_ajena(uow, contexto_acotado) -> None:  # type: ignore[no-untyped-def]
    from app.application.casos_uso.distributivo import EliminarFilaDistributivo
    from app.domain.errors import FueraDeAlcance

    ajena = _fila(uow, facultad_id=FCSEE, carrera_id=MEDICINA)

    with pytest.raises(FueraDeAlcance):
        await EliminarFilaDistributivo(uow)(ajena.id, contexto_acotado)
    assert ajena.id in uow.distributivo.datos
    assert uow.commits == 0


async def test_no_se_captura_la_asignatura_de_una_fila_ajena(  # type: ignore[no-untyped-def]
    uow, contexto_acotado
) -> None:
    from app.application.casos_uso.distributivo import AsignaturaDeFila, CapturarAsignaturas
    from app.domain.errors import FueraDeAlcance

    propia = _fila(uow)
    ajena = _fila(uow, facultad_id=FCSEE, carrera_id=MEDICINA)

    with pytest.raises(FueraDeAlcance):
        await CapturarAsignaturas(uow)(
            [
                AsignaturaDeFila(fila_id=propia.id, asignatura="CALCULO"),
                AsignaturaDeFila(fila_id=ajena.id, asignatura="ANATOMIA"),
            ],
            contexto_acotado,
        )

    # Ni siquiera la propia se guarda: la tanda es una sola transaccion, y sin
    # confirmacion no queda nada. Se comprueba sobre el contador de commits y no
    # sobre la entidad: el doble en memoria comparte el objeto y no simula el
    # `rollback` que si hace PostgreSQL.
    assert uow.commits == 0


async def test_un_administrador_no_se_acota(uow, roles) -> None:  # type: ignore[no-untyped-def]
    from app.application.casos_uso.distributivo import ObtenerFilaDistributivo

    contexto = ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )
    ajena = _fila(uow, facultad_id=FCSEE, carrera_id=MEDICINA)

    assert (await ObtenerFilaDistributivo(uow)(ajena.id, contexto)).fila.id == ajena.id
