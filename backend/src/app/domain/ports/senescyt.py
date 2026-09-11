"""Puerto de consulta de titulos al registro nacional.

Este es el punto de extension mas importante del sistema. El dominio no sabe si
detras hay un raspado web, una API bajo convenio o un archivo de prueba: solo
conoce `ProveedorConsultaTitulos`. Cambiar de mecanismo es registrar otra
implementacion en el contenedor de dependencias.

Sobre la verificacion humana: cuando el proveedor exige un desafio que solo una
persona puede resolver, la implementacion devuelve `DesafioVerificacion`. El
sistema **no intenta resolverlo automaticamente**; lo encola para que un
operador lo atienda desde la interfaz. Es una decision deliberada, documentada
en `docs/SENESCYT.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.domain.value_objects import Cedula


# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class TituloExterno:
    """Titulo tal como lo entrega el proveedor, antes de mapearlo al dominio.

    Es un DTO plano a proposito: aisla al dominio de los cambios de formato del
    proveedor. Si manana el portal renombra un campo, se ajusta el adaptador y
    nada mas.
    """

    denominacion: str
    institucion: str
    tipo: str | None = None
    numero_registro: str | None = None
    fecha_registro: date | None = None
    area: str | None = None
    observacion: str | None = None
    pais: str | None = None
    datos_crudos: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DesafioVerificacion:
    """Desafio que el proveedor exige y que resuelve una persona.

    `imagen_base64` es lo que se muestra al operador en la interfaz;
    `contexto` guarda lo que el adaptador necesite para retomar la sesion
    (cookies, token de formulario) cuando llegue la respuesta.
    """

    desafio_id: str
    tipo: str
    imagen_base64: str | None = None
    instruccion: str = "Transcriba el codigo mostrado en la imagen"
    expira_en_segundos: int = 300
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResultadoConsulta:
    """Respuesta del proveedor a una consulta por cedula."""

    cedula: str
    exitosa: bool
    titulos: list[TituloExterno] = field(default_factory=list)
    nombre_reportado: str | None = None
    """Nombre segun el registro nacional. Sirve para contrastar con el nuestro."""
    desafio: DesafioVerificacion | None = None
    mensaje: str | None = None
    codigo_http: int | None = None
    respuesta_cruda: dict[str, Any] = field(default_factory=dict)

    @property
    def requiere_intervencion(self) -> bool:
        return self.desafio is not None

    @property
    def sin_titulos(self) -> bool:
        return self.exitosa and not self.titulos


# ---------------------------------------------------------------------------
class ProveedorConsultaTitulos(Protocol):
    """Contrato de consulta de titulos por documento de identidad."""

    @property
    def nombre(self) -> str:
        """Identificador del proveedor. Se guarda en cada fila del historico."""
        ...

    @property
    def requiere_verificacion_humana(self) -> bool:
        """`True` si el proveedor puede devolver desafios.

        El planificador lo consulta para decidir si necesita mantener viva la
        cola de resolucion manual.
        """
        ...

    async def consultar(self, cedula: Cedula) -> ResultadoConsulta:
        """Consulta los titulos de una cedula.

        No lanza por errores del proveedor: los reporta en `ResultadoConsulta`
        para que el caso de uso los registre en el historico. Solo lanza ante
        fallos de programacion.
        """
        ...

    async def resolver_desafio(
        self, desafio_id: str, respuesta: str, contexto: dict[str, Any]
    ) -> ResultadoConsulta:
        """Reanuda una consulta con la respuesta que dio el operador humano."""
        ...

    async def verificar_disponibilidad(self) -> bool:
        """Comprueba que el proveedor responde. Se usa antes de arrancar un job."""
        ...

    async def cerrar(self) -> None:
        """Libera recursos (conexiones, sesiones)."""
        ...
