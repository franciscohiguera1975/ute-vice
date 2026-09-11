"""Contrato comun de los casos de uso.

Todo caso de uso del sistema tiene la misma forma:

    resultado = await caso(entrada, contexto)

Esa uniformidad no es estetica. Es la que permitira, en la Fase 11, publicar
cada caso de uso como una *skill* invocable por un agente sin reescribir nada:
basta con derivar el esquema JSON de su dataclass de entrada y leer el permiso
que ya declara. Ver `docs/adr/0006-preparacion-capa-ia.md`.

El caso de uso tampoco sabe que existe HTTP: recibe un `ContextoEjecucion` con
el actor y unos metadatos, y lanza errores de dominio. Quien lo invoque —un
endpoint REST, un comando de consola o un agente— traduce esos errores a su
propio lenguaje.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, TypeVar
from uuid import UUID

from app.domain.entities.auth import Usuario
from app.domain.enums import Permiso
from app.domain.errors import ErrorAutorizacion

TEntrada = TypeVar("TEntrada")
TSalida = TypeVar("TSalida")


@dataclass(frozen=True, slots=True)
class ContextoEjecucion:
    """Quien ejecuta la operacion y desde donde.

    Viaja por toda la capa de aplicacion para resolver autorizacion y auditoria
    sin que los casos de uso tengan que conocer la peticion HTTP.
    """

    actor: Usuario | None = None
    direccion_ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    metadatos: dict[str, Any] = field(default_factory=dict)

    @property
    def actor_id(self) -> UUID | None:
        return self.actor.id if self.actor else None

    @property
    def es_anonimo(self) -> bool:
        return self.actor is None

    @classmethod
    def sistema(cls) -> ContextoEjecucion:
        """Contexto del planificador y otras tareas automaticas.

        No lleva actor: las operaciones que ejecuta ya vienen autorizadas por la
        configuracion del job, no por un usuario concreto.
        """
        return cls(metadatos={"origen": "sistema"})

    @property
    def es_del_sistema(self) -> bool:
        return self.metadatos.get("origen") == "sistema"


class CasoDeUso(ABC, Generic[TEntrada, TSalida]):
    """Base de todos los casos de uso.

    Las subclases declaran `permiso_requerido` y la comprobacion ocurre una sola
    vez, aqui, antes de `_ejecutar`. Ningun caso de uso puede olvidarse de
    autorizar: si el atributo esta puesto, la verificacion es automatica.
    """

    permiso_requerido: ClassVar[Permiso | None] = None
    """Permiso exigido al actor. `None` = operacion publica o ya autorizada."""

    nombre: ClassVar[str] = ""
    """Identificador estable. Sera el nombre de la skill en la Fase 11."""

    descripcion: ClassVar[str] = ""
    """Que hace, en una frase. Alimentara la descripcion de la skill."""

    async def __call__(self, entrada: TEntrada, contexto: ContextoEjecucion) -> TSalida:
        self.autorizar(contexto)
        return await self._ejecutar(entrada, contexto)

    def autorizar(self, contexto: ContextoEjecucion) -> None:
        """Verifica que el actor puede ejecutar esta operacion."""
        if self.permiso_requerido is None:
            return
        if contexto.es_del_sistema:
            return
        if contexto.actor is None:
            raise ErrorAutorizacion(self.permiso_requerido.value)
        if not contexto.actor.puede(self.permiso_requerido):
            raise ErrorAutorizacion(self.permiso_requerido.value)

    @abstractmethod
    async def _ejecutar(self, entrada: TEntrada, contexto: ContextoEjecucion) -> TSalida:
        """Logica del caso de uso. Se ejecuta ya autorizado."""
        ...

    # ------------------------------------------------------------ metadatos
    @classmethod
    def descriptor(cls) -> dict[str, Any]:
        """Metadatos de la operacion, para el catalogo de skills de la Fase 11."""
        return {
            "nombre": cls.nombre or cls.__name__,
            "descripcion": cls.descripcion or (cls.__doc__ or "").strip().split("\n")[0],
            "permiso": cls.permiso_requerido.value if cls.permiso_requerido else None,
            "clase": f"{cls.__module__}.{cls.__qualname__}",
        }


@dataclass(frozen=True, slots=True)
class SinEntrada:
    """Marcador para casos de uso que no reciben parametros."""
