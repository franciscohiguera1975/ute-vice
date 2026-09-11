"""Entidad Titulo: un titulo academico asociado a una persona."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import EstadoTitulo, NivelTitulo, OrigenTitulo
from app.domain.errors import ErrorValidacion
from app.domain.value_objects import ahora_utc, normalizar_texto

#: Palabras clave para inferir el nivel cuando el proveedor no lo entrega
#: normalizado. El orden importa: se evalua de mas especifico a mas general.
_PISTAS_NIVEL: tuple[tuple[NivelTitulo, tuple[str, ...]], ...] = (
    (NivelTitulo.DOCTORADO, ("doctorado", "doctor en", "phd", "ph.d")),
    (NivelTitulo.MAESTRIA, ("maestria", "magister", "master", "msc", "mba")),
    (NivelTitulo.ESPECIALIZACION, ("especialista", "especializacion", "diplomado superior")),
    (
        NivelTitulo.TERCER_NIVEL,
        (
            "ingenier",
            "licenciad",
            "abogad",
            "medic",
            "arquitect",
            "economista",
            "psicolog",
            "odontolog",
            "contador publico",
        ),
    ),
    (NivelTitulo.TECNOLOGICO, ("tecnolog",)),
    (NivelTitulo.TECNICO, ("tecnico superior", "tecnic")),
)


@dataclass(slots=True)
class Titulo:
    """Titulo academico registrado.

    La `huella` es la clave de la reconciliacion: identifica al titulo por su
    contenido normalizado, no por su fila en la base. Gracias a eso el sistema
    distingue "el proveedor devolvio el mismo titulo otra vez" de "el proveedor
    devolvio un titulo distinto", incluso cuando el texto llega con acentuacion
    o espaciado diferente entre consultas.
    """

    persona_id: UUID
    denominacion: str
    institucion: str
    nivel: NivelTitulo = NivelTitulo.NO_DETERMINADO

    numero_registro: str | None = None
    """Numero de registro en el sistema nacional. Identificador natural."""
    fecha_registro: date | None = None
    fecha_graduacion: date | None = None
    area_conocimiento: str | None = None
    pais: str = "ECUADOR"
    observacion_registro: str | None = None
    """Notas del propio registro nacional (p. ej. "titulo reconocido")."""

    origen: OrigenTitulo = OrigenTitulo.SENESCYT
    estado: EstadoTitulo = EstadoTitulo.VIGENTE

    huella: str = ""
    datos_crudos: dict[str, Any] = field(default_factory=dict)
    """Respuesta original del proveedor. Permite reprocesar sin reconsultar."""

    visto_primera_vez_en: datetime = field(default_factory=ahora_utc)
    visto_ultima_vez_en: datetime = field(default_factory=ahora_utc)
    retirado_en: datetime | None = None

    verificado: bool = False
    verificado_por: UUID | None = None
    verificado_en: datetime | None = None

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def __post_init__(self) -> None:
        self.denominacion = " ".join((self.denominacion or "").split())
        self.institucion = " ".join((self.institucion or "").split())

        if not self.denominacion:
            raise ErrorValidacion("La denominacion del titulo es obligatoria", campo="denominacion")
        if not self.institucion:
            raise ErrorValidacion("La institucion es obligatoria", campo="institucion")
        if self.fecha_registro and self.fecha_registro > date.today():
            raise ErrorValidacion(
                "La fecha de registro no puede ser futura", campo="fecha_registro"
            )
        if (
            self.fecha_graduacion
            and self.fecha_registro
            and self.fecha_graduacion > self.fecha_registro
        ):
            raise ErrorValidacion(
                "La graduacion no puede ser posterior al registro", campo="fecha_graduacion"
            )

        if self.nivel is NivelTitulo.NO_DETERMINADO:
            self.nivel = self.inferir_nivel(self.denominacion)
        if not self.huella:
            self.huella = self.calcular_huella(
                denominacion=self.denominacion,
                institucion=self.institucion,
                numero_registro=self.numero_registro,
            )

    # ------------------------------------------------------------- identidad
    @staticmethod
    def calcular_huella(
        *,
        denominacion: str,
        institucion: str,
        numero_registro: str | None,
    ) -> str:
        """Identidad por contenido, estable entre consultas.

        Si hay numero de registro se usa solo eso: es el identificador oficial y
        no cambia aunque el proveedor reformatee el texto del titulo. Sin el, se
        recurre a denominacion + institucion normalizadas.
        """
        if numero_registro and numero_registro.strip():
            semilla = f"reg:{normalizar_texto(numero_registro)}"
        else:
            semilla = f"txt:{normalizar_texto(denominacion)}|{normalizar_texto(institucion)}"
        return hashlib.sha256(semilla.encode()).hexdigest()[:32]

    @staticmethod
    def inferir_nivel(denominacion: str) -> NivelTitulo:
        """Deduce el nivel academico del texto de la denominacion."""
        texto = normalizar_texto(denominacion)
        for nivel, pistas in _PISTAS_NIVEL:
            if any(pista in texto for pista in pistas):
                return nivel
        return NivelTitulo.NO_DETERMINADO

    # ----------------------------------------------------------- comparacion
    def campos_comparables(self) -> dict[str, str]:
        """Campos que, al cambiar, constituyen una modificacion reportable.

        Se comparan normalizados: una tilde distinta en la respuesta del
        proveedor no debe generar una entrada en el historico de cambios.
        """
        return {
            "denominacion": normalizar_texto(self.denominacion),
            "institucion": normalizar_texto(self.institucion),
            "nivel": self.nivel.value,
            "numero_registro": normalizar_texto(self.numero_registro or ""),
            "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else "",
            "area_conocimiento": normalizar_texto(self.area_conocimiento or ""),
            "observacion_registro": normalizar_texto(self.observacion_registro or ""),
        }

    def diferencias_con(self, otro: Titulo) -> dict[str, dict[str, str]]:
        """Campos en los que difiere de `otro`, con valores previo y nuevo."""
        actuales = self.campos_comparables()
        nuevos = otro.campos_comparables()
        return {
            campo: {"anterior": actuales[campo], "nuevo": nuevos[campo]}
            for campo in actuales
            if actuales[campo] != nuevos[campo]
        }

    def es_equivalente_a(self, otro: Titulo) -> bool:
        return self.huella == otro.huella and not self.diferencias_con(otro)

    # ------------------------------------------------------------ mutaciones
    def confirmar_vigencia(self, momento: datetime | None = None) -> None:
        """El proveedor lo devolvio de nuevo: sigue vigente."""
        momento = momento or ahora_utc()
        self.visto_ultima_vez_en = momento
        if self.estado is EstadoTitulo.RETIRADO:
            self.estado = EstadoTitulo.VIGENTE
            self.retirado_en = None
        self.actualizado_en = momento

    def aplicar_actualizacion(self, fuente: Titulo, momento: datetime | None = None) -> None:
        """Copia los campos de contenido desde una version mas reciente.

        No toca identidad, auditoria ni verificacion: solo los datos que el
        proveedor puede haber corregido.
        """
        momento = momento or ahora_utc()
        self.denominacion = fuente.denominacion
        self.institucion = fuente.institucion
        self.nivel = fuente.nivel
        self.numero_registro = fuente.numero_registro
        self.fecha_registro = fuente.fecha_registro
        self.fecha_graduacion = fuente.fecha_graduacion
        self.area_conocimiento = fuente.area_conocimiento
        self.observacion_registro = fuente.observacion_registro
        self.datos_crudos = fuente.datos_crudos
        self.visto_ultima_vez_en = momento
        self.estado = EstadoTitulo.VIGENTE
        self.retirado_en = None
        self.actualizado_en = momento

    def marcar_retirado(self, momento: datetime | None = None) -> None:
        """Dejo de aparecer en el registro nacional.

        No se elimina la fila: un titulo que desaparece es justamente el hallazgo
        que interesa auditar, y borrarlo destruiria la evidencia.
        """
        momento = momento or ahora_utc()
        self.estado = EstadoTitulo.RETIRADO
        self.retirado_en = momento
        self.actualizado_en = momento

    def marcar_verificado(self, usuario_id: UUID, momento: datetime | None = None) -> None:
        momento = momento or ahora_utc()
        self.verificado = True
        self.verificado_por = usuario_id
        self.verificado_en = momento
        if self.estado is EstadoTitulo.POR_VERIFICAR:
            self.estado = EstadoTitulo.VIGENTE
        self.actualizado_en = momento

    # ----------------------------------------------------------- propiedades
    @property
    def es_posgrado(self) -> bool:
        return self.nivel in {
            NivelTitulo.ESPECIALIZACION,
            NivelTitulo.MAESTRIA,
            NivelTitulo.DOCTORADO,
        }

    @property
    def requiere_atencion(self) -> bool:
        """Casos que un analista deberia revisar a mano."""
        return (
            self.estado is EstadoTitulo.RETIRADO
            or self.nivel is NivelTitulo.NO_DETERMINADO
            or (self.origen is OrigenTitulo.MANUAL and not self.verificado)
        )

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Titulo) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
