"""Politica de ritmo de las consultas al proveedor externo.

Esta clase concentra *todas* las decisiones temporales del proceso de
actualizacion. Su proposito es repartir la carga en el tiempo y mantenerla por
debajo de un presupuesto conservador, de modo que una campana sobre miles de
personas se extienda durante dias en lugar de concentrarse en rafagas.

Cuatro mecanismos, todos configurables:

1. **Franja horaria.** Mas actividad en horario de oficina (08:00–17:00), menos
   al caer la tarde (17:00–21:00) y ninguna fuera de esas horas.
2. **Separacion aleatoria.** El intervalo entre consultas se sortea en un rango,
   no es fijo. Un cadencia constante seria a la vez fragil y poco realista.
3. **Presupuesto por hora.** Tope duro que ningun calculo puede exceder.
4. **Retroceso exponencial.** Ante fallos del proveedor se espera cada vez mas,
   hasta que el cortacircuitos detiene el job.

El sistema se identifica siempre ante el proveedor y respeta sus rechazos: si
recibe una senal de limite, se detiene. No hay aqui ningun mecanismo destinado a
enmascarar el origen de las peticiones — esa via se descarto de forma explicita
y la alternativa formal esta descrita en `docs/SENESCYT.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum

from app.domain.entities.consulta import JobCobertura
from app.domain.ports.reloj import FuenteAleatoria


class Franja(StrEnum):
    """Tramo horario en que cae un instante dado."""

    PICO = "PICO"
    """Horario de oficina: maxima actividad."""

    VALLE = "VALLE"
    """Tarde-noche: actividad reducida."""

    INACTIVA = "INACTIVA"
    """Fuera de horario: no se consulta."""


@dataclass(frozen=True, slots=True)
class ConfiguracionRitmo:
    """Parametros de la politica. Copia inmutable de la configuracion."""

    periodo_dias: int = 90
    max_consultas_por_hora: int = 30
    hora_inicio_pico: int = 8
    hora_fin_pico: int = 17
    hora_fin_valle: int = 21
    peso_pico: float = 1.0
    peso_valle: float = 0.35
    demora_minima_segundos: int = 45
    demora_maxima_segundos: int = 240
    retroceso_base_segundos: int = 300
    retroceso_maximo_segundos: int = 7200
    umbral_cortacircuitos: int = 5
    max_intentos_por_persona: int = 3


@dataclass(frozen=True, slots=True)
class DecisionRitmo:
    """Que hacer a continuacion, y por que."""

    puede_consultar: bool
    esperar: timedelta
    franja: Franja
    motivo: str

    @property
    def esperar_segundos(self) -> int:
        return int(self.esperar.total_seconds())


class PoliticaPlanificacion:
    """Traduce la configuracion de ritmo en decisiones concretas.

    Recibe la fuente de aleatoriedad por constructor para que las pruebas puedan
    fijar la semilla y afirmar sobre los intervalos resultantes.
    """

    def __init__(self, config: ConfiguracionRitmo, aleatorio: FuenteAleatoria) -> None:
        self._cfg = config
        self._rnd = aleatorio

    @property
    def configuracion(self) -> ConfiguracionRitmo:
        return self._cfg

    # ------------------------------------------------------- franjas horarias
    def franja_de(self, momento_local: datetime) -> Franja:
        """Franja a la que pertenece un instante en hora local."""
        hora = momento_local.time()
        if time(self._cfg.hora_inicio_pico) <= hora < time(self._cfg.hora_fin_pico):
            return Franja.PICO
        if time(self._cfg.hora_fin_pico) <= hora < time(self._cfg.hora_fin_valle):
            return Franja.VALLE
        return Franja.INACTIVA

    def esta_en_horario(self, momento_local: datetime) -> bool:
        return self.franja_de(momento_local) is not Franja.INACTIVA

    def peso_de(self, franja: Franja) -> float:
        return {
            Franja.PICO: self._cfg.peso_pico,
            Franja.VALLE: self._cfg.peso_valle,
            Franja.INACTIVA: 0.0,
        }[franja]

    def proxima_apertura(self, momento_local: datetime) -> datetime:
        """Siguiente instante en que se reanuda la actividad.

        Si aun no abrio hoy, es hoy a la hora de inicio; si ya cerro, mañana.
        """
        apertura_hoy = momento_local.replace(
            hour=self._cfg.hora_inicio_pico, minute=0, second=0, microsecond=0
        )
        if momento_local < apertura_hoy:
            return apertura_hoy
        return apertura_hoy + timedelta(days=1)

    # ------------------------------------------------------------- intervalo
    def intervalo_hasta_siguiente(self, franja: Franja) -> timedelta:
        """Separacion aleatoria antes de la siguiente consulta.

        El sorteo es uniforme dentro del rango configurado y luego se divide por
        el peso de la franja: en horario valle, con peso 0.35, las esperas se
        alargan casi el triple, que es exactamente el efecto buscado.
        """
        if franja is Franja.INACTIVA:
            return timedelta(hours=1)

        base = self._rnd.uniforme(
            float(self._cfg.demora_minima_segundos),
            float(self._cfg.demora_maxima_segundos),
        )
        peso = max(self.peso_de(franja), 0.01)
        segundos = base / peso

        # El presupuesto horario impone un piso al intervalo: aunque el sorteo
        # salga bajo, nunca se supera el tope duro de consultas por hora.
        piso = 3600.0 / max(self._cfg.max_consultas_por_hora, 1)
        return timedelta(seconds=max(segundos, piso))

    def retroceso(self, intentos_fallidos: int) -> timedelta:
        """Espera tras un fallo: crece exponencialmente y se acota."""
        if intentos_fallidos <= 0:
            return timedelta(0)
        segundos = self._cfg.retroceso_base_segundos * (2 ** (intentos_fallidos - 1))
        segundos = min(segundos, self._cfg.retroceso_maximo_segundos)
        # Se le suma un jitter de hasta el 20% para que varios trabajadores no
        # reintenten todos en el mismo instante.
        jitter = self._rnd.uniforme(0.0, segundos * 0.2)
        return timedelta(seconds=segundos + jitter)

    # ------------------------------------------------------------ presupuesto
    def presupuesto_restante(self, consultas_en_la_hora: int) -> int:
        return max(0, self._cfg.max_consultas_por_hora - consultas_en_la_hora)

    def decidir(
        self,
        *,
        momento_local: datetime,
        consultas_en_la_hora: int,
        fallos_consecutivos: int = 0,
    ) -> DecisionRitmo:
        """Decision completa: ¿se consulta ahora o se espera, y cuanto?"""
        franja = self.franja_de(momento_local)

        if franja is Franja.INACTIVA:
            espera = self.proxima_apertura(momento_local) - momento_local
            return DecisionRitmo(
                puede_consultar=False,
                esperar=espera,
                franja=franja,
                motivo=(
                    "Fuera del horario configurado "
                    f"({self._cfg.hora_inicio_pico:02d}:00–{self._cfg.hora_fin_valle:02d}:00)"
                ),
            )

        if self.presupuesto_restante(consultas_en_la_hora) <= 0:
            # Espera hasta el inicio de la hora siguiente.
            siguiente_hora = (momento_local + timedelta(hours=1)).replace(
                minute=0, second=0, microsecond=0
            )
            return DecisionRitmo(
                puede_consultar=False,
                esperar=siguiente_hora - momento_local,
                franja=franja,
                motivo=(
                    f"Presupuesto agotado: {consultas_en_la_hora}/"
                    f"{self._cfg.max_consultas_por_hora} consultas en esta hora"
                ),
            )

        if fallos_consecutivos > 0:
            return DecisionRitmo(
                puede_consultar=True,
                esperar=self.retroceso(fallos_consecutivos),
                franja=franja,
                motivo=f"Retroceso tras {fallos_consecutivos} fallo(s) consecutivo(s)",
            )

        return DecisionRitmo(
            puede_consultar=True,
            esperar=self.intervalo_hasta_siguiente(franja),
            franja=franja,
            motivo=f"Ritmo normal en franja {franja.value}",
        )

    # ----------------------------------------------------------- factibilidad
    def consultas_diarias_estimadas(self) -> int:
        """Capacidad diaria segun las franjas y el presupuesto por hora.

        Se usa para avisar al operador, antes de arrancar, si el periodo elegido
        alcanza para cubrir el padron.
        """
        horas_pico = max(0, self._cfg.hora_fin_pico - self._cfg.hora_inicio_pico)
        horas_valle = max(0, self._cfg.hora_fin_valle - self._cfg.hora_fin_pico)

        # En cada franja, el ritmo real es el menor entre lo que permite el
        # intervalo medio y lo que permite el presupuesto horario.
        medio = (self._cfg.demora_minima_segundos + self._cfg.demora_maxima_segundos) / 2

        def por_hora(peso: float) -> float:
            if peso <= 0 or medio <= 0:
                return 0.0
            return min(3600.0 / (medio / peso), float(self._cfg.max_consultas_por_hora))

        return int(
            horas_pico * por_hora(self._cfg.peso_pico)
            + horas_valle * por_hora(self._cfg.peso_valle)
        )

    def evaluar_factibilidad(self, total_personas: int) -> EvaluacionFactibilidad:
        """¿Alcanza el periodo para cubrir a todo el padron?"""
        diarias = self.consultas_diarias_estimadas()
        capacidad = diarias * self._cfg.periodo_dias
        dias_necesarios = (total_personas + diarias - 1) // diarias if diarias else 0
        return EvaluacionFactibilidad(
            total_personas=total_personas,
            consultas_diarias_estimadas=diarias,
            capacidad_del_periodo=capacidad,
            dias_necesarios=dias_necesarios,
            periodo_dias=self._cfg.periodo_dias,
        )

    def evaluar_avance(self, job: JobCobertura, ahora: datetime) -> EvaluacionAvance:
        """Contrasta el avance real del job con el esperado a estas alturas."""
        esperado = job.periodo.progreso(ahora)
        real = (job.procesados / job.total_items) if job.total_items else 0.0
        requerido = job.ritmo_requerido_por_hora(ahora)
        return EvaluacionAvance(
            avance_real=round(real, 4),
            avance_esperado=round(esperado, 4),
            ritmo_requerido_por_hora=requerido,
            presupuesto_por_hora=self._cfg.max_consultas_por_hora,
        )


@dataclass(frozen=True, slots=True)
class EvaluacionFactibilidad:
    total_personas: int
    consultas_diarias_estimadas: int
    capacidad_del_periodo: int
    dias_necesarios: int
    periodo_dias: int

    @property
    def es_factible(self) -> bool:
        return self.capacidad_del_periodo >= self.total_personas

    @property
    def advertencia(self) -> str | None:
        if self.es_factible:
            return None
        return (
            f"Con el ritmo configurado se cubren ~{self.consultas_diarias_estimadas} "
            f"personas por dia: {self.total_personas} personas requieren "
            f"~{self.dias_necesarios} dias y el periodo es de {self.periodo_dias}. "
            "Amplie el periodo o revise el presupuesto por hora."
        )


@dataclass(frozen=True, slots=True)
class EvaluacionAvance:
    avance_real: float
    avance_esperado: float
    ritmo_requerido_por_hora: float
    presupuesto_por_hora: int

    @property
    def va_atrasado(self) -> bool:
        # Se tolera un 5% de desviacion antes de reportar atraso.
        return self.avance_real < self.avance_esperado - 0.05

    @property
    def ritmo_es_alcanzable(self) -> bool:
        return self.ritmo_requerido_por_hora <= self.presupuesto_por_hora

    @property
    def advertencia(self) -> str | None:
        if not self.va_atrasado:
            return None
        base = f"Avance {self.avance_real:.1%} frente a {self.avance_esperado:.1%} esperado."
        if not self.ritmo_es_alcanzable:
            return (
                f"{base} El ritmo necesario ({self.ritmo_requerido_por_hora}/h) supera "
                f"el presupuesto ({self.presupuesto_por_hora}/h): el periodo no cerrara "
                "completo. Amplie el periodo en lugar de subir el ritmo."
            )
        return f"{base} Aun es recuperable dentro del presupuesto actual."
