"""Pruebas de la politica de ritmo de consultas.

Verifica los cuatro mecanismos que reparten la carga en el tiempo: franja
horaria, separacion aleatoria, presupuesto por hora y retroceso ante fallos.

Las pruebas son posibles porque la politica recibe el reloj y la fuente de azar
por constructor. Si llamara a `datetime.now()` y a `random` directamente, no
habria forma de comprobar el comportamiento a las 03:00 sin esperar a esa hora.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.ports.reloj import AleatorioDelSistema
from app.domain.services.planificacion import (
    ConfiguracionRitmo,
    Franja,
    PoliticaPlanificacion,
)

pytestmark = pytest.mark.unit


def hora(h: int, m: int = 0) -> datetime:
    """Instante local del 4 de septiembre de 2026 a la hora indicada."""
    return datetime(2026, 9, 4, h, m, tzinfo=UTC)


@pytest.fixture
def config() -> ConfiguracionRitmo:
    return ConfiguracionRitmo(
        periodo_dias=90,
        max_consultas_por_hora=30,
        hora_inicio_pico=8,
        hora_fin_pico=17,
        hora_fin_valle=21,
        peso_pico=1.0,
        peso_valle=0.35,
        demora_minima_segundos=45,
        demora_maxima_segundos=240,
        retroceso_base_segundos=300,
        retroceso_maximo_segundos=7200,
        umbral_cortacircuitos=5,
    )


@pytest.fixture
def politica(config: ConfiguracionRitmo) -> PoliticaPlanificacion:
    return PoliticaPlanificacion(config, AleatorioDelSistema(semilla=42))


class TestFranjasHorarias:
    """El requisito: mas consultas de 08 a 17, menos de 17 a 21, ninguna fuera."""

    @pytest.mark.parametrize(
        ("h", "esperada"),
        [
            (0, Franja.INACTIVA),
            (7, Franja.INACTIVA),
            (8, Franja.PICO),
            (12, Franja.PICO),
            (16, Franja.PICO),
            (17, Franja.VALLE),
            (19, Franja.VALLE),
            (20, Franja.VALLE),
            (21, Franja.INACTIVA),
            (23, Franja.INACTIVA),
        ],
    )
    def test_clasifica_la_hora_en_su_franja(
        self, politica: PoliticaPlanificacion, h: int, esperada: Franja
    ) -> None:
        assert politica.franja_de(hora(h)) is esperada

    def test_los_limites_son_los_esperados(self, politica: PoliticaPlanificacion) -> None:
        assert politica.franja_de(hora(7, 59)) is Franja.INACTIVA
        assert politica.franja_de(hora(8, 0)) is Franja.PICO
        assert politica.franja_de(hora(16, 59)) is Franja.PICO
        assert politica.franja_de(hora(17, 0)) is Franja.VALLE
        assert politica.franja_de(hora(20, 59)) is Franja.VALLE
        assert politica.franja_de(hora(21, 0)) is Franja.INACTIVA

    def test_el_peso_del_valle_es_menor_que_el_del_pico(
        self, politica: PoliticaPlanificacion
    ) -> None:
        assert politica.peso_de(Franja.PICO) > politica.peso_de(Franja.VALLE) > 0
        assert politica.peso_de(Franja.INACTIVA) == 0.0

    def test_calcula_la_proxima_apertura(self, politica: PoliticaPlanificacion) -> None:
        # De madrugada, abre hoy mismo a las 08:00.
        assert politica.proxima_apertura(hora(3)) == hora(8)
        # Ya cerrado, abre manana a las 08:00.
        assert politica.proxima_apertura(hora(22)) == hora(8) + timedelta(days=1)


class TestSeparacionEntreConsultas:
    """El requisito: las peticiones no salen todas de golpe, sino espaciadas."""

    def test_el_intervalo_es_aleatorio_dentro_del_rango(
        self, politica: PoliticaPlanificacion
    ) -> None:
        """El intervalo varia entre consultas: no hay una cadencia constante.

        El limite inferior efectivo no es la demora minima configurada (45 s)
        sino el piso que impone el presupuesto horario: con 30 consultas/hora,
        ninguna separacion baja de 120 s. Los sorteos por debajo de ese valor se
        recortan, asi que el piso aparece repetido — y eso es lo correcto.
        """
        intervalos = [
            politica.intervalo_hasta_siguiente(Franja.PICO).total_seconds() for _ in range(60)
        ]
        piso = 3600 / 30

        assert len(set(intervalos)) > 10, "el intervalo deberia variar entre consultas"
        assert all(piso <= i <= 240 for i in intervalos)
        assert max(intervalos) > piso, "algunos sorteos deben superar el piso"

    def test_en_valle_las_esperas_son_mas_largas(self, politica: PoliticaPlanificacion) -> None:
        """Peso 0.35 alarga la espera casi el triple: menos consultas por hora."""
        pico = [politica.intervalo_hasta_siguiente(Franja.PICO).total_seconds() for _ in range(200)]
        valle = [
            politica.intervalo_hasta_siguiente(Franja.VALLE).total_seconds() for _ in range(200)
        ]
        assert sum(valle) / len(valle) > sum(pico) / len(pico) * 2

    def test_el_presupuesto_horario_impone_un_piso_al_intervalo(self) -> None:
        """Aunque el sorteo salga bajo, nunca se supera el tope de consultas
        por hora: es un limite duro, no una sugerencia."""
        config = ConfiguracionRitmo(
            max_consultas_por_hora=10,  # -> 360 s minimo entre consultas
            demora_minima_segundos=1,
            demora_maxima_segundos=2,
        )
        politica = PoliticaPlanificacion(config, AleatorioDelSistema(semilla=1))
        for _ in range(50):
            assert politica.intervalo_hasta_siguiente(Franja.PICO).total_seconds() >= 360


class TestPresupuestoPorHora:
    def test_descuenta_lo_ya_consumido(self, politica: PoliticaPlanificacion) -> None:
        assert politica.presupuesto_restante(0) == 30
        assert politica.presupuesto_restante(25) == 5
        assert politica.presupuesto_restante(30) == 0
        assert politica.presupuesto_restante(45) == 0

    def test_al_agotarse_se_espera_a_la_hora_siguiente(
        self, politica: PoliticaPlanificacion
    ) -> None:
        decision = politica.decidir(momento_local=hora(10, 20), consultas_en_la_hora=30)
        assert not decision.puede_consultar
        assert "Presupuesto agotado" in decision.motivo
        # 40 minutos hasta las 11:00.
        assert decision.esperar == timedelta(minutes=40)


class TestRetrocesoExponencial:
    def test_la_espera_crece_con_cada_fallo(self, politica: PoliticaPlanificacion) -> None:
        esperas = [politica.retroceso(n).total_seconds() for n in range(1, 6)]
        assert esperas == sorted(esperas)
        assert esperas[0] >= 300
        assert esperas[4] >= 4800

    def test_la_espera_esta_acotada(self, politica: PoliticaPlanificacion) -> None:
        """Sin tope, el retroceso llegaria a dias y el job quedaria muerto."""
        # 7200 de tope + hasta 20% de jitter.
        assert politica.retroceso(20).total_seconds() <= 7200 * 1.2

    def test_sin_fallos_no_hay_retroceso(self, politica: PoliticaPlanificacion) -> None:
        assert politica.retroceso(0) == timedelta(0)


class TestDecisionCompleta:
    def test_fuera_de_horario_no_consulta_y_espera_a_la_apertura(
        self, politica: PoliticaPlanificacion
    ) -> None:
        decision = politica.decidir(momento_local=hora(3), consultas_en_la_hora=0)
        assert not decision.puede_consultar
        assert decision.franja is Franja.INACTIVA
        assert "Fuera del horario" in decision.motivo
        assert decision.esperar == timedelta(hours=5)

    def test_en_horario_y_con_presupuesto_consulta(self, politica: PoliticaPlanificacion) -> None:
        decision = politica.decidir(momento_local=hora(10), consultas_en_la_hora=5)
        assert decision.puede_consultar
        assert decision.franja is Franja.PICO
        assert decision.esperar_segundos > 0

    def test_tras_un_fallo_consulta_pero_espera_mas(self, politica: PoliticaPlanificacion) -> None:
        normal = politica.decidir(momento_local=hora(10), consultas_en_la_hora=0)
        con_fallos = politica.decidir(
            momento_local=hora(10), consultas_en_la_hora=0, fallos_consecutivos=3
        )
        assert con_fallos.puede_consultar
        assert con_fallos.esperar > normal.esperar
        assert "Retroceso" in con_fallos.motivo


class TestFactibilidad:
    """Antes de arrancar, el sistema avisa si el periodo no alcanza."""

    def test_estima_la_capacidad_diaria(self, politica: PoliticaPlanificacion) -> None:
        diarias = politica.consultas_diarias_estimadas()
        assert 0 < diarias <= 30 * 13  # 13 horas operativas, tope de 30/h

    def test_reporta_factible_cuando_el_periodo_alcanza(
        self, politica: PoliticaPlanificacion
    ) -> None:
        evaluacion = politica.evaluar_factibilidad(total_personas=500)
        assert evaluacion.es_factible
        assert evaluacion.advertencia is None

    def test_advierte_cuando_el_periodo_no_alcanza(self) -> None:
        """Con un padron grande y un periodo corto, la respuesta correcta es
        ampliar el periodo, no acelerar el ritmo. La advertencia lo dice."""
        config = ConfiguracionRitmo(periodo_dias=2, max_consultas_por_hora=5)
        politica = PoliticaPlanificacion(config, AleatorioDelSistema(semilla=1))
        evaluacion = politica.evaluar_factibilidad(total_personas=100_000)
        assert not evaluacion.es_factible
        assert evaluacion.advertencia is not None
        assert "Amplie el periodo" in evaluacion.advertencia


class TestEvaluacionDeAvance:
    def test_detecta_atraso_frente_a_lo_esperado(self, politica: PoliticaPlanificacion) -> None:
        from app.domain.entities.consulta import JobCobertura
        from app.domain.value_objects import PeriodoCobertura

        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        job = JobCobertura(nombre="prueba", periodo=PeriodoCobertura.desde(inicio, dias=100))
        job.total_items = 1000
        job.completados = 100  # 10% hecho...

        # ...cuando ya transcurrio el 50% del periodo.
        evaluacion = politica.evaluar_avance(job, inicio + timedelta(days=50))
        assert evaluacion.va_atrasado
        assert evaluacion.advertencia is not None

    def test_no_reporta_atraso_dentro_de_la_tolerancia(
        self, politica: PoliticaPlanificacion
    ) -> None:
        from app.domain.entities.consulta import JobCobertura
        from app.domain.value_objects import PeriodoCobertura

        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        job = JobCobertura(nombre="prueba", periodo=PeriodoCobertura.desde(inicio, dias=100))
        job.total_items = 1000
        job.completados = 500

        evaluacion = politica.evaluar_avance(job, inicio + timedelta(days=50))
        assert not evaluacion.va_atrasado
        assert evaluacion.advertencia is None
