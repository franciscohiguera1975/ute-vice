"""Pruebas del reconciliador de titulos.

Este servicio responde a la pregunta central del sistema: *¿que cambio desde la
ultima consulta?*. Cada uno de los cuatro casos que distingue tiene su prueba,
porque un error aqui produce un historico que miente — y el historico es la
razon de ser de la herramienta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.conftest import hacer_titulo

from app.domain.enums import EstadoTitulo, NivelTitulo, OrigenTitulo, TipoCambio
from app.domain.ports.senescyt import TituloExterno
from app.domain.services.reconciliador import ReconciliadorTitulos

pytestmark = pytest.mark.unit

MOMENTO = datetime(2026, 9, 4, tzinfo=UTC)


@pytest.fixture
def reconciliador() -> ReconciliadorTitulos:
    return ReconciliadorTitulos()


@pytest.fixture
def persona_id():  # type: ignore[no-untyped-def]
    return uuid4()


def externo(
    denominacion: str = "INGENIERO EN SISTEMAS",
    institucion: str = "UNIVERSIDAD TECNOLOGICA EQUINOCCIAL",
    registro: str | None = "1234-2015-567890",
    **extra: object,
) -> TituloExterno:
    return TituloExterno(
        denominacion=denominacion,
        institucion=institucion,
        numero_registro=registro,
        **extra,  # type: ignore[arg-type]
    )


class TestTitulosNuevos:
    def test_primera_consulta_registra_todos_los_titulos(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[],
            externos=[externo(), externo("MAGISTER EN EDUCACION", registro="999-2020-1")],
            momento=MOMENTO,
        )
        assert len(plan.nuevos) == 2
        assert plan.hubo_cambios
        assert all(c.tipo is TipoCambio.TITULO_NUEVO for c in plan.cambios)

    def test_solo_el_titulo_nuevo_se_agrega(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        existente = hacer_titulo(persona_id)
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo(), externo("MAGISTER EN GERENCIA", registro="777-2021-3")],
            momento=MOMENTO,
        )
        assert len(plan.nuevos) == 1
        assert len(plan.confirmados) == 1
        assert plan.nuevos[0].denominacion == "MAGISTER EN GERENCIA"


class TestSinCambios:
    def test_el_mismo_titulo_solo_se_confirma(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        existente = hacer_titulo(persona_id)
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo()],
            momento=MOMENTO,
        )
        assert not plan.nuevos and not plan.actualizados and not plan.retirados
        assert len(plan.confirmados) == 1
        assert not plan.hubo_cambios
        assert plan.cambios[0].tipo is TipoCambio.SIN_CAMBIOS

    def test_la_acentuacion_distinta_no_cuenta_como_cambio(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """El proveedor devuelve el texto con acentuacion inconsistente.

        Sin normalizacion, cada consulta reportaria una modificacion falsa y el
        historico quedaria inservible para detectar cambios reales.
        """
        existente = hacer_titulo(persona_id, denominacion="INGENIERIA EN SISTEMAS INFORMATICOS")
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo("Ingeniería  en   Sistemas Informáticos")],
            momento=MOMENTO,
        )
        assert not plan.hubo_cambios
        assert len(plan.confirmados) == 1

    def test_la_huella_se_basa_en_el_registro_cuando_existe(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Con numero de registro, un cambio de redaccion es una *modificacion*,
        no un titulo distinto: el registro es el identificador oficial."""
        existente = hacer_titulo(persona_id, denominacion="INGENIERO EN SISTEMAS")
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo("INGENIERO DE SISTEMAS INFORMATICOS")],
            momento=MOMENTO,
        )
        assert not plan.nuevos
        assert len(plan.actualizados) == 1


class TestTitulosModificados:
    def test_detecta_y_describe_el_campo_cambiado(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        existente = hacer_titulo(persona_id, institucion="UNIVERSIDAD CENTRAL DEL ECUADOR")
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo(institucion="UNIVERSIDAD TECNOLOGICA EQUINOCCIAL")],
            momento=MOMENTO,
        )
        assert len(plan.actualizados) == 1
        cambio = plan.cambios[0]
        assert cambio.tipo is TipoCambio.TITULO_MODIFICADO
        assert "institucion" in cambio.detalle["campos"]

    def test_la_entidad_queda_actualizada_en_el_plan(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        existente = hacer_titulo(persona_id, area_conocimiento=None)
        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[existente],
            externos=[externo(area="INGENIERIA, INDUSTRIA Y CONSTRUCCION")],
            momento=MOMENTO,
        )
        assert plan.actualizados[0].area_conocimiento == "INGENIERIA, INDUSTRIA Y CONSTRUCCION"
        assert plan.actualizados[0].visto_ultima_vez_en == MOMENTO


class TestTitulosRetirados:
    def test_marca_retirado_lo_que_el_proveedor_dejo_de_reportar(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Un titulo que desaparece del registro nacional es el hallazgo que
        motiva la auditoria: se marca, nunca se borra."""
        existente = hacer_titulo(persona_id)
        plan = reconciliador.reconciliar(
            persona_id=persona_id, existentes=[existente], externos=[], momento=MOMENTO
        )
        assert len(plan.retirados) == 1
        assert plan.retirados[0].estado is EstadoTitulo.RETIRADO
        assert plan.retirados[0].retirado_en == MOMENTO
        assert plan.cambios[0].tipo is TipoCambio.TITULO_RETIRADO

    def test_no_retira_los_titulos_cargados_a_mano(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Un titulo con respaldo documental fisico no debe marcarse retirado
        porque el registro nacional no lo liste."""
        manual = hacer_titulo(
            persona_id, origen=OrigenTitulo.MANUAL, estado=EstadoTitulo.POR_VERIFICAR
        )
        plan = reconciliador.reconciliar(
            persona_id=persona_id, existentes=[manual], externos=[], momento=MOMENTO
        )
        assert not plan.retirados
        assert manual.estado is EstadoTitulo.POR_VERIFICAR

    def test_un_titulo_que_reaparece_vuelve_a_vigente(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        retirado = hacer_titulo(persona_id, estado=EstadoTitulo.RETIRADO)
        retirado.retirado_en = MOMENTO
        reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[retirado],
            externos=[externo()],
            momento=MOMENTO,
        )
        assert retirado.estado is EstadoTitulo.VIGENTE
        assert retirado.retirado_en is None

    def test_puede_desactivarse_ante_una_respuesta_parcial(self, persona_id) -> None:
        """Si la consulta fue incompleta, tratar lo ausente como retirado
        produciria falsos positivos alarmantes."""
        reconciliador = ReconciliadorTitulos(marcar_ausentes_como_retirados=False)
        existente = hacer_titulo(persona_id)
        plan = reconciliador.reconciliar(
            persona_id=persona_id, existentes=[existente], externos=[], momento=MOMENTO
        )
        assert not plan.retirados
        assert existente.estado is EstadoTitulo.VIGENTE


class TestInferenciaDeNivel:
    @pytest.mark.parametrize(
        ("tipo", "denominacion", "esperado"),
        [
            ("CUARTO NIVEL - DOCTORADO", "DOCTOR EN EDUCACION", NivelTitulo.DOCTORADO),
            ("CUARTO NIVEL", "MAGISTER EN GERENCIA", NivelTitulo.MAESTRIA),
            ("TERCER NIVEL", "INGENIERO CIVIL", NivelTitulo.TERCER_NIVEL),
            (None, "MAGISTER EN EDUCACION SUPERIOR", NivelTitulo.MAESTRIA),
            (None, "DOCTOR EN CIENCIAS (PHD)", NivelTitulo.DOCTORADO),
            (None, "LICENCIADO EN COMUNICACION", NivelTitulo.TERCER_NIVEL),
            (None, "TECNOLOGO EN ELECTRONICA", NivelTitulo.TECNOLOGICO),
            (None, "ESPECIALISTA EN MEDICINA INTERNA", NivelTitulo.ESPECIALIZACION),
            (None, "TITULO SIN PISTAS RECONOCIBLES", NivelTitulo.NO_DETERMINADO),
        ],
    )
    def test_deduce_el_nivel(
        self,
        reconciliador: ReconciliadorTitulos,
        persona_id,
        tipo: str | None,
        denominacion: str,
        esperado: NivelTitulo,
    ) -> None:
        titulo = reconciliador.mapear(
            externo(denominacion, tipo=tipo), persona_id=persona_id, momento=MOMENTO
        )
        assert titulo.nivel is esperado

    def test_la_categoria_del_proveedor_no_se_contradice_con_el_texto(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Una denominacion de tercer nivel reportada como cuarto nivel es un
        dato contradictorio. Se conserva la categoria oficial del registro en
        lugar de degradarla por el texto."""
        titulo = reconciliador.mapear(
            externo("INGENIERO EN SISTEMAS", tipo="CUARTO NIVEL"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is NivelTitulo.MAESTRIA


class TestEscenarioCompleto:
    def test_combina_los_cuatro_casos_en_una_sola_consulta(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """El escenario realista: algo se mantiene, algo cambia, algo aparece y
        algo desaparece, todo en la misma respuesta del proveedor."""
        sin_cambios = hacer_titulo(persona_id, numero_registro="A-1")
        a_modificar = hacer_titulo(
            persona_id,
            denominacion="MAGISTER EN EDUCACION",
            institucion="UNIVERSIDAD CENTRAL",
            numero_registro="B-2",
        )
        a_retirar = hacer_titulo(persona_id, denominacion="TITULO REVOCADO", numero_registro="C-3")

        plan = reconciliador.reconciliar(
            persona_id=persona_id,
            existentes=[sin_cambios, a_modificar, a_retirar],
            externos=[
                externo(registro="A-1"),
                externo(
                    "MAGISTER EN EDUCACION",
                    institucion="UNIVERSIDAD TECNOLOGICA EQUINOCCIAL",
                    registro="B-2",
                ),
                externo("DOCTOR EN EDUCACION", registro="D-4"),
            ],
            momento=MOMENTO,
        )

        assert plan.resumen() == {
            "nuevos": 1,
            "actualizados": 1,
            "confirmados": 1,
            "retirados": 1,
        }
        tipos = {c.tipo for c in plan.cambios}
        assert tipos == {
            TipoCambio.TITULO_NUEVO,
            TipoCambio.TITULO_MODIFICADO,
            TipoCambio.TITULO_RETIRADO,
        }
        assert plan.total_reportado == 3


class TestCategoriasAmpliasDelProveedor:
    """El `tipo` del proveedor no siempre identifica el nivel.

    "CUARTO NIVEL" agrupa especializaciones, maestrias y doctorados. Tomarlo al
    pie de la letra clasifica mal a una parte del personal, y el nivel academico
    es justamente lo que se reporta a las autoridades.
    """

    @pytest.mark.parametrize(
        ("denominacion", "esperado"),
        [
            ("ESPECIALISTA EN MEDICINA INTERNA", NivelTitulo.ESPECIALIZACION),
            ("MAGISTER EN EDUCACION SUPERIOR", NivelTitulo.MAESTRIA),
            ("DOCTOR EN CIENCIAS (PHD)", NivelTitulo.DOCTORADO),
        ],
    )
    def test_cuarto_nivel_se_afina_con_la_denominacion(
        self,
        reconciliador: ReconciliadorTitulos,
        persona_id,
        denominacion: str,
        esperado: NivelTitulo,
    ) -> None:
        titulo = reconciliador.mapear(
            externo(denominacion, tipo="CUARTO NIVEL"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is esperado

    def test_cuarto_nivel_sin_pistas_cae_a_maestria(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Es el valor mas frecuente de la categoria: el mejor supuesto."""
        titulo = reconciliador.mapear(
            externo("TITULO DE POSGRADO SIN DENOMINACION RECONOCIBLE", tipo="CUARTO NIVEL"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is NivelTitulo.MAESTRIA

    def test_un_tipo_especifico_manda_sobre_la_denominacion(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Si el proveedor precisa el nivel, se le cree: es el dato oficial."""
        titulo = reconciliador.mapear(
            externo("PROGRAMA AVANZADO DE GESTION", tipo="MAESTRIA"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is NivelTitulo.MAESTRIA

    def test_tercer_nivel_tambien_se_afina(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        titulo = reconciliador.mapear(
            externo("TECNOLOGO EN ELECTRONICA", tipo="TERCER NIVEL"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is NivelTitulo.TECNOLOGICO

    def test_una_denominacion_de_posgrado_no_degrada_un_tercer_nivel(
        self, reconciliador: ReconciliadorTitulos, persona_id
    ) -> None:
        """Simetrico del caso anterior: la categoria acota en ambos sentidos."""
        titulo = reconciliador.mapear(
            externo("MAGISTER EN ALGO", tipo="TERCER NIVEL"),
            persona_id=persona_id,
            momento=MOMENTO,
        )
        assert titulo.nivel is NivelTitulo.TERCER_NIVEL
