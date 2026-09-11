"""Entidad Persona: el empleado de la UTE cuyos titulos se validan."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.enums import EstadoConsulta, TipoDocumento, TipoVinculacion
from app.domain.errors import ErrorValidacion
from app.domain.value_objects import (
    Cedula,
    Email,
    NombrePersona,
    PeriodoCobertura,
    ahora_utc,
)


@dataclass(slots=True)
class Persona:
    """Empleado de la institucion.

    La entidad conoce su propio historial de consulta (`ultima_consulta_*`).
    Eso permite responder "¿toca reconsultar a esta persona?" sin ir a la tabla
    de logs — la decision de planificacion se resuelve con datos que la persona
    ya lleva encima.
    """

    cedula: Cedula
    nombre: NombrePersona
    tipo_documento: TipoDocumento = TipoDocumento.CEDULA
    email_institucional: Email | None = None
    email_personal: Email | None = None
    telefono: str | None = None

    # --- Vinculacion laboral ---
    tipo_vinculacion: TipoVinculacion = TipoVinculacion.OTRO
    unidad: str | None = None
    """Facultad, carrera o dependencia. Texto libre hasta la Fase 09."""
    cargo: str | None = None
    codigo_empleado: str | None = None
    fecha_ingreso: date | None = None

    fecha_nacimiento: date | None = None
    activo: bool = True
    observaciones: str | None = None

    # --- Trazabilidad de consultas ---
    ultima_consulta_en: datetime | None = None
    ultima_consulta_estado: EstadoConsulta | None = None
    ultima_consulta_exitosa_en: datetime | None = None
    total_consultas: int = 0
    titulos_registrados: int = 0

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        if self.fecha_nacimiento and self.fecha_nacimiento > date.today():
            raise ErrorValidacion(
                "La fecha de nacimiento no puede ser futura", campo="fecha_nacimiento"
            )
        if (
            self.fecha_ingreso
            and self.fecha_nacimiento
            and self.fecha_ingreso < self.fecha_nacimiento
        ):
            raise ErrorValidacion(
                "El ingreso no puede ser anterior al nacimiento", campo="fecha_ingreso"
            )

    # ----------------------------------------------------------- propiedades
    @property
    def nombre_completo(self) -> str:
        return self.nombre.completo

    @property
    def clave_busqueda(self) -> str:
        """Texto normalizado que alimenta el indice de busqueda difusa."""
        partes = [self.nombre.normalizado, self.cedula.valor]
        if self.unidad:
            partes.append(self.unidad.lower())
        if self.codigo_empleado:
            partes.append(self.codigo_empleado.lower())
        return " ".join(partes)

    @property
    def nunca_consultada(self) -> bool:
        return self.ultima_consulta_en is None

    # ------------------------------------------------- politica de cobertura
    def requiere_consulta(
        self,
        periodo: PeriodoCobertura,
        *,
        ahora: datetime | None = None,
        reintentar_errores_tras: timedelta = timedelta(days=1),
    ) -> bool:
        """¿Corresponde consultar a esta persona dentro del periodo vigente?

        Esta es la regla que impide reconsultar a alguien antes de haber cubierto
        al resto del padron:

        1. Persona inactiva → nunca.
        2. Nunca consultada → si, es prioritaria.
        3. Ultima consulta anterior al periodo → si, el periodo previo ya cerro.
        4. Consultada con exito dentro del periodo → no, ya esta cubierta.
        5. Consultada con error dentro del periodo → si, pero solo despues del
           margen de reintento, para no insistir sobre un fallo reciente.

        La comparacion es contra el **inicio** del periodo, no `contiene()`. Son
        distintas en dos situaciones que importan: una consulta hecha justo en
        el instante del corte —el extremo final de `contiene()` es exclusivo— y
        una consulta posterior al cierre del periodo. En ambos casos la persona
        esta cubierta, y `contiene()` diria que no.
        """
        if not self.activo:
            return False
        if self.ultima_consulta_en is None:
            return True
        if self.ultima_consulta_en < periodo.inicio:
            return True

        if self.ultima_consulta_estado and self.ultima_consulta_estado.es_error:
            ahora = ahora or ahora_utc()
            return ahora - self.ultima_consulta_en >= reintentar_errores_tras

        return False

    def prioridad_consulta(self, ahora: datetime | None = None) -> tuple[int, float]:
        """Clave de ordenamiento: menor valor = se consulta antes.

        Devuelve `(nivel, antiguedad_invertida)`. Nunca consultadas primero,
        luego las que fallaron, luego por antiguedad. El planificador ordena por
        esta clave y despues aplica el desorden aleatorio dentro de cada nivel.
        """
        ahora = ahora or ahora_utc()
        if self.ultima_consulta_en is None:
            return (0, 0.0)
        antiguedad = (ahora - self.ultima_consulta_en).total_seconds()
        nivel = 1 if (self.ultima_consulta_estado and self.ultima_consulta_estado.es_error) else 2
        return (nivel, -antiguedad)

    # ------------------------------------------------------------ mutaciones
    def registrar_consulta(
        self,
        estado: EstadoConsulta,
        *,
        momento: datetime | None = None,
        titulos_registrados: int | None = None,
    ) -> None:
        """Actualiza la trazabilidad tras una consulta al proveedor."""
        momento = momento or ahora_utc()
        self.ultima_consulta_en = momento
        self.ultima_consulta_estado = estado
        self.total_consultas += 1
        if estado in {EstadoConsulta.EXITO, EstadoConsulta.SIN_DATOS}:
            self.ultima_consulta_exitosa_en = momento
        if titulos_registrados is not None:
            self.titulos_registrados = titulos_registrados
        self.actualizado_en = momento

    def actualizar_datos(
        self,
        *,
        nombre: NombrePersona | None = None,
        email_institucional: Email | None = None,
        email_personal: Email | None = None,
        telefono: str | None = None,
        tipo_vinculacion: TipoVinculacion | None = None,
        unidad: str | None = None,
        cargo: str | None = None,
        codigo_empleado: str | None = None,
        fecha_ingreso: date | None = None,
        fecha_nacimiento: date | None = None,
        observaciones: str | None = None,
    ) -> None:
        """Aplica solo los campos recibidos; `None` significa "sin cambio"."""
        if nombre is not None:
            self.nombre = nombre
        if email_institucional is not None:
            self.email_institucional = email_institucional
        if email_personal is not None:
            self.email_personal = email_personal
        if telefono is not None:
            self.telefono = telefono
        if tipo_vinculacion is not None:
            self.tipo_vinculacion = tipo_vinculacion
        if unidad is not None:
            self.unidad = unidad
        if cargo is not None:
            self.cargo = cargo
        if codigo_empleado is not None:
            self.codigo_empleado = codigo_empleado
        if fecha_ingreso is not None:
            self.fecha_ingreso = fecha_ingreso
        if fecha_nacimiento is not None:
            self.fecha_nacimiento = fecha_nacimiento
        if observaciones is not None:
            self.observaciones = observaciones
        self.actualizado_en = ahora_utc()
        self.__post_init__()

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = ahora_utc()

    def activar(self) -> None:
        self.activo = True
        self.actualizado_en = ahora_utc()

    # --------------------------------------------------------- privacidad
    def seudonimo(self) -> str:
        """Identificador estable y no reversible, para analitica agregada.

        Permite contar y agrupar sin exponer la cedula en tableros o en un
        eventual contexto de IA.
        """
        return hashlib.sha256(f"persona:{self.id}".encode()).hexdigest()[:16]

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Persona) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
