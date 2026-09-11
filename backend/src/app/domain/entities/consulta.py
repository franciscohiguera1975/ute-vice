"""Entidades del proceso de consulta al registro nacional de titulos.

Tres piezas:

* `ConsultaLog` — historico inmutable. Una fila por intento, exitoso o no. Es la
  tabla que responde "¿que paso con la cedula X el dia Y?".
* `JobCobertura` — campana que recorre todo el padron dentro de un periodo. Es
  reanudable: sabe exactamente donde quedo tras dias de ejecucion.
* `ItemJob` — una persona dentro de un job. Es el cursor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import (
    EstadoConsulta,
    EstadoItemJob,
    EstadoJob,
    TipoCambio,
)
from app.domain.errors import ConflictoDeEstado
from app.domain.value_objects import Cedula, PeriodoCobertura, ahora_utc


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CambioDetectado:
    """Diferencia concreta hallada al reconciliar una consulta."""

    tipo: TipoCambio
    titulo_id: UUID | None
    denominacion: str
    detalle: dict[str, Any] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo.value,
            "titulo_id": str(self.titulo_id) if self.titulo_id else None,
            "denominacion": self.denominacion,
            "detalle": self.detalle,
        }


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ConsultaLog:
    """Registro historico de un intento de consulta. Inmutable una vez cerrado.

    Se escribe **siempre**, pase lo que pase: exito, error de red, rechazo del
    proveedor o cedula invalida. Esa es la razon de existir de la tabla — sin
    ella no hay forma de auditar por que el dato de una persona esta desfasado.
    """

    persona_id: UUID
    cedula: Cedula
    estado: EstadoConsulta

    job_id: UUID | None = None
    proveedor: str = "desconocido"
    intento: int = 1

    iniciado_en: datetime = field(default_factory=ahora_utc)
    finalizado_en: datetime | None = None
    duracion_ms: int | None = None

    # --- Resultado ---
    titulos_encontrados: int = 0
    titulos_nuevos: int = 0
    titulos_actualizados: int = 0
    titulos_retirados: int = 0
    cambios: list[CambioDetectado] = field(default_factory=list)

    # --- Diagnostico ---
    mensaje: str | None = None
    tipo_error: str | None = None
    codigo_http: int | None = None
    respuesta_cruda: dict[str, Any] | None = None

    ejecutado_por: UUID | None = None
    """Usuario que lanzo la consulta manual. `None` si fue el planificador."""

    id: UUID = field(default_factory=uuid4)

    # ------------------------------------------------------------- factorias
    @classmethod
    def iniciar(
        cls,
        *,
        persona_id: UUID,
        cedula: Cedula,
        proveedor: str,
        job_id: UUID | None = None,
        intento: int = 1,
        ejecutado_por: UUID | None = None,
    ) -> ConsultaLog:
        return cls(
            persona_id=persona_id,
            cedula=cedula,
            estado=EstadoConsulta.EXITO,  # provisional; se fija al cerrar
            proveedor=proveedor,
            job_id=job_id,
            intento=intento,
            ejecutado_por=ejecutado_por,
        )

    # -------------------------------------------------------------- cierre
    def cerrar_con_exito(
        self,
        *,
        titulos_encontrados: int,
        cambios: list[CambioDetectado],
        respuesta_cruda: dict[str, Any] | None = None,
        momento: datetime | None = None,
    ) -> None:
        self.estado = EstadoConsulta.EXITO if titulos_encontrados else EstadoConsulta.SIN_DATOS
        self.titulos_encontrados = titulos_encontrados
        self.cambios = cambios
        self.titulos_nuevos = sum(1 for c in cambios if c.tipo is TipoCambio.TITULO_NUEVO)
        self.titulos_actualizados = sum(
            1 for c in cambios if c.tipo is TipoCambio.TITULO_MODIFICADO
        )
        self.titulos_retirados = sum(1 for c in cambios if c.tipo is TipoCambio.TITULO_RETIRADO)
        self.respuesta_cruda = respuesta_cruda
        self._sellar(momento)

    def cerrar_con_error(
        self,
        estado: EstadoConsulta,
        *,
        mensaje: str,
        tipo_error: str | None = None,
        codigo_http: int | None = None,
        momento: datetime | None = None,
    ) -> None:
        self.estado = estado
        self.mensaje = mensaje[:2000]
        self.tipo_error = tipo_error
        self.codigo_http = codigo_http
        self._sellar(momento)

    def cerrar_esperando_desafio(self, *, desafio_id: str, momento: datetime | None = None) -> None:
        """El proveedor pidio verificacion humana: queda en cola, no es un fallo."""
        self.estado = EstadoConsulta.DESAFIO_PENDIENTE
        self.mensaje = "Requiere resolucion manual del desafio de verificacion"
        self.respuesta_cruda = {"desafio_id": desafio_id}
        self._sellar(momento)

    def _sellar(self, momento: datetime | None = None) -> None:
        self.finalizado_en = momento or ahora_utc()
        self.duracion_ms = int((self.finalizado_en - self.iniciado_en).total_seconds() * 1000)

    # ---------------------------------------------------------- propiedades
    @property
    def hubo_cambios(self) -> bool:
        return bool(self.cambios) and any(
            c.tipo is not TipoCambio.SIN_CAMBIOS for c in self.cambios
        )

    @property
    def resumen(self) -> str:
        if self.estado.es_error:
            return f"{self.estado.value}: {self.mensaje or 'sin detalle'}"
        if not self.hubo_cambios:
            return f"{self.titulos_encontrados} titulo(s), sin cambios"
        partes: list[str] = []
        if self.titulos_nuevos:
            partes.append(f"{self.titulos_nuevos} nuevo(s)")
        if self.titulos_actualizados:
            partes.append(f"{self.titulos_actualizados} modificado(s)")
        if self.titulos_retirados:
            partes.append(f"{self.titulos_retirados} retirado(s)")
        return ", ".join(partes)


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ItemJob:
    """Una persona dentro de un job de cobertura. Es el cursor reanudable."""

    job_id: UUID
    persona_id: UUID
    orden: int
    """Posicion en la secuencia barajada. Fija el recorrido del job."""

    estado: EstadoItemJob = EstadoItemJob.PENDIENTE
    programado_para: datetime | None = None
    """Momento mas temprano en que puede procesarse. Lo fija el planificador."""

    intentos: int = 0
    ultimo_log_id: UUID | None = None
    ultimo_error: str | None = None
    desafio_id: str | None = None
    procesado_en: datetime | None = None

    id: UUID = field(default_factory=uuid4)

    def esta_listo(self, ahora: datetime | None = None) -> bool:
        if self.estado is not EstadoItemJob.PENDIENTE:
            return False
        if self.programado_para is None:
            return True
        return (ahora or ahora_utc()) >= self.programado_para

    def tomar(self) -> None:
        if self.estado is not EstadoItemJob.PENDIENTE:
            raise ConflictoDeEstado(f"El item esta en estado {self.estado.value}; no puede tomarse")
        self.estado = EstadoItemJob.EN_PROCESO
        self.intentos += 1

    def completar(self, log_id: UUID, momento: datetime | None = None) -> None:
        self.estado = EstadoItemJob.COMPLETADO
        self.ultimo_log_id = log_id
        self.procesado_en = momento or ahora_utc()
        self.ultimo_error = None

    def fallar(self, log_id: UUID, mensaje: str, *, reintentable: bool, max_intentos: int) -> None:
        """Devuelve el item a la cola o lo da por perdido."""
        self.ultimo_log_id = log_id
        self.ultimo_error = mensaje[:500]
        if reintentable and self.intentos < max_intentos:
            self.estado = EstadoItemJob.PENDIENTE
        else:
            self.estado = EstadoItemJob.FALLIDO
            self.procesado_en = ahora_utc()

    def esperar_desafio(self, desafio_id: str, log_id: UUID) -> None:
        self.estado = EstadoItemJob.ESPERANDO_DESAFIO
        self.desafio_id = desafio_id
        self.ultimo_log_id = log_id

    def reencolar(self, *, retraso: timedelta | None = None) -> None:
        self.estado = EstadoItemJob.PENDIENTE
        self.desafio_id = None
        if retraso:
            self.programado_para = ahora_utc() + retraso

    def omitir(self, motivo: str) -> None:
        self.estado = EstadoItemJob.OMITIDO
        self.ultimo_error = motivo[:500]
        self.procesado_en = ahora_utc()


# ---------------------------------------------------------------------------
@dataclass(slots=True)
class JobCobertura:
    """Campana de actualizacion que recorre el padron dentro de un periodo.

    Diseñado para vivir dias: guarda contadores y un cortacircuitos, de modo que
    reiniciar el proceso no pierde el avance ni reconsulta lo ya hecho.
    """

    nombre: str
    periodo: PeriodoCobertura
    estado: EstadoJob = EstadoJob.BORRADOR

    total_items: int = 0
    completados: int = 0
    fallidos: int = 0
    omitidos: int = 0
    esperando_desafio: int = 0

    fallos_consecutivos: int = 0
    """Alimenta el cortacircuitos. Se reinicia con cada exito."""
    pausado_automaticamente: bool = False
    motivo_pausa: str | None = None

    proxima_ejecucion_en: datetime | None = None
    ultima_actividad_en: datetime | None = None
    iniciado_en: datetime | None = None
    finalizado_en: datetime | None = None

    configuracion: dict[str, Any] = field(default_factory=dict)
    """Instantanea de la politica al crear el job: hace reproducible el resultado."""

    creado_por: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)

    # ------------------------------------------------------- ciclo de vida
    def programar(self, total_items: int) -> None:
        if self.estado is not EstadoJob.BORRADOR:
            raise ConflictoDeEstado(
                f"Solo un job en BORRADOR puede programarse (esta en {self.estado.value})"
            )
        if total_items <= 0:
            raise ConflictoDeEstado("No hay personas que consultar en este periodo")
        self.total_items = total_items
        self.estado = EstadoJob.PROGRAMADO

    def iniciar(self, momento: datetime | None = None) -> None:
        if self.estado not in {EstadoJob.PROGRAMADO, EstadoJob.PAUSADO}:
            raise ConflictoDeEstado(f"No se puede iniciar un job en estado {self.estado.value}")
        momento = momento or ahora_utc()
        self.estado = EstadoJob.EN_CURSO
        self.iniciado_en = self.iniciado_en or momento
        self.ultima_actividad_en = momento
        self.pausado_automaticamente = False
        self.motivo_pausa = None
        self.fallos_consecutivos = 0

    def pausar(self, motivo: str, *, automatico: bool = False) -> None:
        if self.estado.es_terminal:
            raise ConflictoDeEstado(f"El job ya esta {self.estado.value}")
        self.estado = EstadoJob.PAUSADO
        self.motivo_pausa = motivo
        self.pausado_automaticamente = automatico

    def reanudar(self) -> None:
        if self.estado is not EstadoJob.PAUSADO:
            raise ConflictoDeEstado("Solo un job pausado puede reanudarse")
        self.iniciar()

    def cancelar(self, motivo: str | None = None) -> None:
        if self.estado.es_terminal:
            raise ConflictoDeEstado(f"El job ya esta {self.estado.value}")
        self.estado = EstadoJob.CANCELADO
        self.motivo_pausa = motivo
        self.finalizado_en = ahora_utc()

    def completar(self, momento: datetime | None = None) -> None:
        self.estado = EstadoJob.COMPLETADO
        self.finalizado_en = momento or ahora_utc()

    # ------------------------------------------------------------ progreso
    def registrar_resultado(self, estado: EstadoConsulta, *, umbral_cortacircuitos: int) -> None:
        """Contabiliza un resultado y aplica el cortacircuitos si toca.

        El cortacircuitos existe para protegernos a ambos lados: si el proveedor
        empieza a rechazar o a fallar, seguir insistiendo solo empeora las cosas.
        Se pausa el job y se deja constancia del motivo para revision humana.
        """
        self.ultima_actividad_en = ahora_utc()

        if estado in {EstadoConsulta.EXITO, EstadoConsulta.SIN_DATOS}:
            self.completados += 1
            self.fallos_consecutivos = 0
        elif estado is EstadoConsulta.DESAFIO_PENDIENTE:
            self.esperando_desafio += 1
        elif estado is EstadoConsulta.ERROR_DATOS:
            self.omitidos += 1
            self.fallos_consecutivos = 0
        else:
            self.fallidos += 1
            if estado.cuenta_para_cortacircuitos:
                self.fallos_consecutivos += 1

        if self.fallos_consecutivos >= umbral_cortacircuitos:
            self.pausar(
                f"Cortacircuitos: {self.fallos_consecutivos} fallos consecutivos "
                "del proveedor. Requiere revision antes de reanudar.",
                automatico=True,
            )

    def registrar_desafio_resuelto(self) -> None:
        self.esperando_desafio = max(0, self.esperando_desafio - 1)

    @property
    def procesados(self) -> int:
        return self.completados + self.fallidos + self.omitidos

    @property
    def pendientes(self) -> int:
        return max(0, self.total_items - self.procesados - self.esperando_desafio)

    @property
    def porcentaje_avance(self) -> float:
        if self.total_items == 0:
            return 0.0
        return round(self.procesados / self.total_items * 100, 2)

    @property
    def esta_cubierto(self) -> bool:
        """Todo el padron del periodo fue procesado."""
        return self.total_items > 0 and self.pendientes == 0 and self.esperando_desafio == 0

    def ritmo_requerido_por_hora(self, ahora: datetime | None = None) -> float:
        """Consultas por hora necesarias para cerrar el periodo a tiempo.

        El planificador la compara con el presupuesto configurado: si el ritmo
        requerido lo supera, el periodo es demasiado corto para el padron y hay
        que avisar al operador en lugar de acelerar en silencio.
        """
        ahora = ahora or ahora_utc()
        restantes = self.pendientes
        if restantes == 0:
            return 0.0
        horas = max((self.periodo.fin - ahora).total_seconds() / 3600, 1.0)
        return round(restantes / horas, 2)

    def a_resumen(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "nombre": self.nombre,
            "estado": self.estado.value,
            "periodo": str(self.periodo),
            "total": self.total_items,
            "completados": self.completados,
            "fallidos": self.fallidos,
            "omitidos": self.omitidos,
            "esperando_desafio": self.esperando_desafio,
            "pendientes": self.pendientes,
            "avance": self.porcentaje_avance,
            "pausado_automaticamente": self.pausado_automaticamente,
            "motivo_pausa": self.motivo_pausa,
        }

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, JobCobertura) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
