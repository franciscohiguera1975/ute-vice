"""Pruebas de la regla de cobertura del padron.

El requisito, literal: *no volver a consultar a una persona antes de que todas
hayan sido consultadas en el periodo*. Se implementa con dos piezas que se
prueban aqui — `PeriodoCobertura` y `Persona.requiere_consulta()` — y con la
maquina de estados del job.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tests.conftest import CEDULAS_VALIDAS, hacer_persona

from app.domain.entities.consulta import JobCobertura
from app.domain.enums import EstadoConsulta, EstadoItemJob, EstadoJob
from app.domain.errors import ConflictoDeEstado
from app.domain.value_objects import PeriodoCobertura

pytestmark = pytest.mark.unit

INICIO = datetime(2026, 6, 1, tzinfo=UTC)
PERIODO = PeriodoCobertura.desde(INICIO, dias=90)
DENTRO = INICIO + timedelta(days=10)
FUERA = INICIO - timedelta(days=5)


class TestRequiereConsulta:
    def test_una_persona_nunca_consultada_es_prioritaria(self) -> None:
        persona = hacer_persona()
        assert persona.nunca_consultada
        assert persona.requiere_consulta(PERIODO, ahora=DENTRO)

    def test_una_persona_ya_consultada_en_el_periodo_no_se_repite(self) -> None:
        """Esta es la regla central: cubierta dentro del periodo, se excluye."""
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.EXITO, momento=DENTRO)
        assert not persona.requiere_consulta(PERIODO, ahora=DENTRO + timedelta(days=1))

    def test_sin_titulos_tambien_cuenta_como_cubierta(self) -> None:
        """`SIN_DATOS` es una respuesta valida: la persona quedo verificada."""
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.SIN_DATOS, momento=DENTRO)
        assert not persona.requiere_consulta(PERIODO, ahora=DENTRO + timedelta(days=1))

    def test_una_consulta_del_periodo_anterior_no_cuenta(self) -> None:
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.EXITO, momento=FUERA)
        assert persona.requiere_consulta(PERIODO, ahora=DENTRO)

    def test_una_persona_inactiva_nunca_se_consulta(self) -> None:
        persona = hacer_persona(activo=False)
        assert not persona.requiere_consulta(PERIODO, ahora=DENTRO)

    def test_un_error_se_reintenta_pero_no_de_inmediato(self) -> None:
        """Insistir sobre un fallo reciente solo desperdicia presupuesto."""
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.ERROR_RED, momento=DENTRO)

        # Una hora despues: aun no.
        assert not persona.requiere_consulta(PERIODO, ahora=DENTRO + timedelta(hours=1))
        # Al dia siguiente: si.
        assert persona.requiere_consulta(PERIODO, ahora=DENTRO + timedelta(days=2))

    def test_una_cedula_rechazada_por_el_proveedor_tambien_se_reintenta(self) -> None:
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.ERROR_DATOS, momento=DENTRO)
        assert persona.requiere_consulta(PERIODO, ahora=DENTRO + timedelta(days=2))


class TestPrioridadDeConsulta:
    def test_ordena_nunca_consultadas_primero_luego_errores_luego_antiguedad(self) -> None:
        nunca = hacer_persona(CEDULAS_VALIDAS[0])

        con_error = hacer_persona(CEDULAS_VALIDAS[1])
        con_error.registrar_consulta(EstadoConsulta.ERROR_RED, momento=DENTRO)

        reciente = hacer_persona(CEDULAS_VALIDAS[2])
        reciente.registrar_consulta(EstadoConsulta.EXITO, momento=DENTRO + timedelta(days=5))

        antigua = hacer_persona(CEDULAS_VALIDAS[3])
        antigua.registrar_consulta(EstadoConsulta.EXITO, momento=FUERA)

        ahora = DENTRO + timedelta(days=10)
        ordenadas = sorted(
            [reciente, antigua, nunca, con_error],
            key=lambda p: p.prioridad_consulta(ahora),
        )
        assert ordenadas[0] is nunca
        assert ordenadas[1] is con_error
        # Entre las exitosas, primero la mas antigua.
        assert ordenadas[2] is antigua
        assert ordenadas[3] is reciente


class TestMaquinaDeEstadosDelJob:
    @pytest.fixture
    def job(self) -> JobCobertura:
        return JobCobertura(nombre="Campana de prueba", periodo=PERIODO)

    def test_el_ciclo_normal_avanza_hasta_completado(self, job: JobCobertura) -> None:
        assert job.estado is EstadoJob.BORRADOR
        job.programar(total_items=100)
        assert job.estado is EstadoJob.PROGRAMADO
        job.iniciar(DENTRO)
        assert job.estado is EstadoJob.EN_CURSO
        job.completar(DENTRO + timedelta(days=30))
        assert job.estado is EstadoJob.COMPLETADO
        assert job.estado.es_terminal

    def test_no_se_programa_un_job_sin_personas(self, job: JobCobertura) -> None:
        """Si no hay candidatos, la cobertura del periodo ya esta completa."""
        with pytest.raises(ConflictoDeEstado, match="No hay personas"):
            job.programar(total_items=0)

    def test_pausar_y_reanudar(self, job: JobCobertura) -> None:
        job.programar(50)
        job.iniciar(DENTRO)
        job.pausar("revision del operador")
        assert job.estado is EstadoJob.PAUSADO
        assert not job.estado.admite_procesamiento
        job.reanudar()
        assert job.estado is EstadoJob.EN_CURSO

    def test_un_job_cancelado_no_se_reanuda(self, job: JobCobertura) -> None:
        job.programar(50)
        job.iniciar(DENTRO)
        job.cancelar("ya no se necesita")
        with pytest.raises(ConflictoDeEstado):
            job.reanudar()

    def test_no_se_inicia_desde_borrador(self, job: JobCobertura) -> None:
        with pytest.raises(ConflictoDeEstado, match="No se puede iniciar"):
            job.iniciar(DENTRO)


class TestCortacircuitos:
    """Ante fallos repetidos del proveedor, el job se detiene solo.

    Insistir cuando el otro lado esta caido o nos esta rechazando empeora las
    cosas para ambos. El cortacircuitos protege al proveedor y evita quemar
    presupuesto en errores.
    """

    @pytest.fixture
    def job(self) -> JobCobertura:
        job = JobCobertura(nombre="prueba", periodo=PERIODO)
        job.programar(100)
        job.iniciar(DENTRO)
        return job

    def test_se_abre_tras_el_umbral_de_fallos_consecutivos(self, job: JobCobertura) -> None:
        for _ in range(5):
            job.registrar_resultado(EstadoConsulta.ERROR_PROVEEDOR, umbral_cortacircuitos=5)
        assert job.estado is EstadoJob.PAUSADO
        assert job.pausado_automaticamente
        assert "Cortacircuitos" in (job.motivo_pausa or "")

    def test_un_exito_reinicia_la_cuenta(self, job: JobCobertura) -> None:
        for _ in range(4):
            job.registrar_resultado(EstadoConsulta.ERROR_RED, umbral_cortacircuitos=5)
        job.registrar_resultado(EstadoConsulta.EXITO, umbral_cortacircuitos=5)
        assert job.fallos_consecutivos == 0

        for _ in range(4):
            job.registrar_resultado(EstadoConsulta.ERROR_RED, umbral_cortacircuitos=5)
        assert job.estado is EstadoJob.EN_CURSO  # no llego al umbral

    def test_una_cedula_invalida_no_abre_el_cortacircuitos(self, job: JobCobertura) -> None:
        """Un dato malo es culpa nuestra, no del proveedor: no debe detener la
        campana entera."""
        for _ in range(10):
            job.registrar_resultado(EstadoConsulta.ERROR_DATOS, umbral_cortacircuitos=5)
        assert job.estado is EstadoJob.EN_CURSO
        assert job.omitidos == 10

    def test_un_rechazo_del_proveedor_si_cuenta(self, job: JobCobertura) -> None:
        for _ in range(5):
            job.registrar_resultado(EstadoConsulta.RECHAZADO, umbral_cortacircuitos=5)
        assert job.estado is EstadoJob.PAUSADO


class TestProgresoDelJob:
    @pytest.fixture
    def job(self) -> JobCobertura:
        job = JobCobertura(nombre="prueba", periodo=PERIODO)
        job.programar(10)
        job.iniciar(DENTRO)
        return job

    def test_calcula_avance_y_pendientes(self, job: JobCobertura) -> None:
        for _ in range(3):
            job.registrar_resultado(EstadoConsulta.EXITO, umbral_cortacircuitos=99)
        job.registrar_resultado(EstadoConsulta.ERROR_DATOS, umbral_cortacircuitos=99)

        assert job.completados == 3
        assert job.omitidos == 1
        assert job.procesados == 4
        assert job.pendientes == 6
        assert job.porcentaje_avance == 40.0
        assert not job.esta_cubierto

    def test_esta_cubierto_al_procesar_todo(self, job: JobCobertura) -> None:
        for _ in range(10):
            job.registrar_resultado(EstadoConsulta.EXITO, umbral_cortacircuitos=99)
        assert job.esta_cubierto
        assert job.pendientes == 0

    def test_un_desafio_pendiente_impide_dar_por_cubierto(self, job: JobCobertura) -> None:
        """Mientras alguien espera resolucion humana, el padron no esta cubierto."""
        for _ in range(9):
            job.registrar_resultado(EstadoConsulta.EXITO, umbral_cortacircuitos=99)
        job.registrar_resultado(EstadoConsulta.DESAFIO_PENDIENTE, umbral_cortacircuitos=99)
        assert not job.esta_cubierto
        assert job.esperando_desafio == 1

        job.registrar_desafio_resuelto()
        job.registrar_resultado(EstadoConsulta.EXITO, umbral_cortacircuitos=99)
        assert job.esta_cubierto

    def test_calcula_el_ritmo_necesario_para_cerrar_a_tiempo(self, job: JobCobertura) -> None:
        ritmo = job.ritmo_requerido_por_hora(PERIODO.fin - timedelta(hours=10))
        assert ritmo == pytest.approx(1.0, abs=0.01)  # 10 pendientes en 10 horas


class TestItemJob:
    """El item es el cursor que hace reanudable una campana de varios dias."""

    @pytest.fixture
    def item(self):  # type: ignore[no-untyped-def]
        from uuid import uuid4

        from app.domain.entities.consulta import ItemJob

        return ItemJob(job_id=uuid4(), persona_id=uuid4(), orden=0)

    def test_esta_listo_solo_si_esta_pendiente(self, item) -> None:
        assert item.esta_listo(DENTRO)
        item.tomar()
        assert not item.esta_listo(DENTRO)

    def test_respeta_la_programacion_futura(self, item) -> None:
        item.programado_para = DENTRO + timedelta(hours=2)
        assert not item.esta_listo(DENTRO)
        assert item.esta_listo(DENTRO + timedelta(hours=3))

    def test_no_puede_tomarse_dos_veces(self, item) -> None:
        item.tomar()
        with pytest.raises(ConflictoDeEstado):
            item.tomar()

    def test_un_fallo_reintentable_vuelve_a_la_cola(self, item) -> None:
        from uuid import uuid4

        item.tomar()
        item.fallar(uuid4(), "error de red", reintentable=True, max_intentos=3)
        assert item.estado is EstadoItemJob.PENDIENTE
        assert item.intentos == 1

    def test_se_da_por_perdido_al_agotar_los_intentos(self, item) -> None:
        from uuid import uuid4

        for _ in range(3):
            item.tomar()
            item.fallar(uuid4(), "error", reintentable=True, max_intentos=3)
        assert item.estado is EstadoItemJob.FALLIDO

    def test_un_fallo_no_reintentable_termina_de_inmediato(self, item) -> None:
        from uuid import uuid4

        item.tomar()
        item.fallar(uuid4(), "cedula invalida", reintentable=False, max_intentos=3)
        assert item.estado is EstadoItemJob.FALLIDO
        assert item.estado.es_terminal


class TestBordesDelPeriodo:
    """Casos limite de la regla de cobertura.

    La comprobacion se hace contra el inicio del periodo, no con `contiene()`:
    el extremo final de un periodo es exclusivo, asi que una consulta realizada
    exactamente en ese instante quedaria fuera de su propio periodo.
    """

    def test_una_consulta_en_el_instante_del_corte_cuenta_como_cubierta(self) -> None:
        # Ventana movil que termina ahora mismo, como la de una consulta puntual.
        ahora = datetime(2026, 7, 1, tzinfo=UTC)
        ventana = PeriodoCobertura(inicio=ahora - timedelta(days=90), fin=ahora)

        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.EXITO, momento=ahora)

        assert not persona.requiere_consulta(ventana, ahora=ahora)

    def test_una_consulta_posterior_al_cierre_tambien_cuenta(self) -> None:
        """Puede ocurrir con una consulta forzada tras cerrarse el periodo del
        job: la persona esta cubierta de sobra, no le toca otra vez."""
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.EXITO, momento=PERIODO.fin + timedelta(days=1))
        assert not persona.requiere_consulta(PERIODO, ahora=PERIODO.fin + timedelta(days=2))

    def test_una_consulta_justo_antes_del_inicio_no_cuenta(self) -> None:
        persona = hacer_persona()
        persona.registrar_consulta(
            EstadoConsulta.EXITO, momento=PERIODO.inicio - timedelta(seconds=1)
        )
        assert persona.requiere_consulta(PERIODO, ahora=DENTRO)

    def test_una_consulta_en_el_instante_de_inicio_si_cuenta(self) -> None:
        persona = hacer_persona()
        persona.registrar_consulta(EstadoConsulta.EXITO, momento=PERIODO.inicio)
        assert not persona.requiere_consulta(PERIODO, ahora=DENTRO)
