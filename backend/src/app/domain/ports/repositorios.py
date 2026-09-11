"""Puertos de persistencia.

Son `Protocol`, no clases base: la implementacion de infraestructura no hereda
de nada del dominio, solo cumple la forma. Eso mantiene la flecha de dependencia
apuntando hacia adentro — el dominio define el contrato y la infraestructura se
adapta a el, nunca al reves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from app.domain.entities.auth import Rol, TokenRefresco, Usuario
from app.domain.entities.consulta import ConsultaLog, ItemJob, JobCobertura
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import (
    EstadoConsulta,
    EstadoJob,
    EstadoTitulo,
    NivelTitulo,
    TipoVinculacion,
)
from app.domain.value_objects import Cedula, Email

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Paginacion y filtros
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Paginacion:
    """Parametros de paginacion y ordenamiento."""

    pagina: int = 1
    tamano: int = 25
    ordenar_por: str | None = None
    descendente: bool = False

    def __post_init__(self) -> None:
        from app.domain.errors import ErrorValidacion

        if self.pagina < 1:
            raise ErrorValidacion("La pagina debe ser mayor o igual a 1", campo="pagina")
        if not 1 <= self.tamano <= 200:
            raise ErrorValidacion("El tamano de pagina debe estar entre 1 y 200", campo="tamano")

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.tamano

    @property
    def limite(self) -> int:
        return self.tamano


@dataclass(frozen=True, slots=True)
class Pagina(Generic[T]):
    """Rebanada de resultados con su metadato de navegacion."""

    items: list[T]
    total: int
    pagina: int
    tamano: int

    @property
    def total_paginas(self) -> int:
        return (self.total + self.tamano - 1) // self.tamano if self.tamano else 0

    @property
    def tiene_siguiente(self) -> bool:
        return self.pagina < self.total_paginas

    @property
    def tiene_anterior(self) -> bool:
        return self.pagina > 1

    @classmethod
    def vacia(cls, paginacion: Paginacion) -> Pagina[T]:
        return cls(items=[], total=0, pagina=paginacion.pagina, tamano=paginacion.tamano)


@dataclass(frozen=True, slots=True)
class FiltroPersonas:
    """Criterios de busqueda de personas.

    Se declara como objeto en lugar de una lista de argumentos sueltos: agregar
    un criterio nuevo no cambia la firma del repositorio ni la de los casos de
    uso que lo atraviesan.
    """

    texto: str | None = None
    """Busqueda difusa sobre nombre, cedula, unidad y codigo de empleado."""
    cedula: str | None = None
    unidad: str | None = None
    tipo_vinculacion: TipoVinculacion | None = None
    activo: bool | None = None
    con_titulos: bool | None = None
    """`False` aisla a quienes no tienen ningun titulo registrado."""
    nunca_consultadas: bool | None = None
    estado_ultima_consulta: EstadoConsulta | None = None
    consultadas_desde: datetime | None = None
    consultadas_hasta: datetime | None = None


@dataclass(frozen=True, slots=True)
class FiltroTitulos:
    texto: str | None = None
    persona_id: UUID | None = None
    nivel: NivelTitulo | None = None
    estado: EstadoTitulo | None = None
    institucion: str | None = None
    verificado: bool | None = None
    requiere_atencion: bool | None = None
    registro_desde: date | None = None
    registro_hasta: date | None = None


@dataclass(frozen=True, slots=True)
class FiltroLogs:
    persona_id: UUID | None = None
    job_id: UUID | None = None
    cedula: str | None = None
    estado: EstadoConsulta | None = None
    solo_con_cambios: bool = False
    solo_errores: bool = False
    desde: datetime | None = None
    hasta: datetime | None = None


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------


class RepositorioUsuarios(Protocol):
    async def obtener(self, usuario_id: UUID) -> Usuario | None: ...
    async def obtener_por_email(self, email: Email) -> Usuario | None: ...
    async def obtener_por_externo(self, proveedor: str, identificador: str) -> Usuario | None: ...
    async def listar(
        self,
        paginacion: Paginacion,
        *,
        texto: str | None = None,
        activo: bool | None = None,
        rol: str | None = None,
    ) -> Pagina[Usuario]: ...
    async def agregar(self, usuario: Usuario) -> Usuario: ...
    async def actualizar(self, usuario: Usuario) -> Usuario: ...
    async def eliminar(self, usuario_id: UUID) -> None: ...
    async def existe_email(self, email: Email, *, excluyendo: UUID | None = None) -> bool: ...
    async def contar_superusuarios_activos(self) -> int: ...


class RepositorioRoles(Protocol):
    async def obtener(self, rol_id: UUID) -> Rol | None: ...
    async def obtener_por_codigo(self, codigo: str) -> Rol | None: ...
    async def listar_todos(self) -> list[Rol]: ...
    async def agregar(self, rol: Rol) -> Rol: ...
    async def actualizar(self, rol: Rol) -> Rol: ...
    async def eliminar(self, rol_id: UUID) -> None: ...
    async def contar_usuarios(self, rol_id: UUID) -> int: ...


class RepositorioTokensRefresco(Protocol):
    async def obtener_por_hash(self, hash_token: str) -> TokenRefresco | None: ...
    async def agregar(self, token: TokenRefresco) -> TokenRefresco: ...
    async def actualizar(self, token: TokenRefresco) -> TokenRefresco: ...
    async def revocar_todos_de(self, usuario_id: UUID) -> int: ...
    async def eliminar_expirados(self, antes_de: datetime) -> int: ...


class RepositorioPersonas(Protocol):
    async def obtener(self, persona_id: UUID) -> Persona | None: ...
    async def obtener_por_cedula(self, cedula: Cedula) -> Persona | None: ...
    async def listar(self, filtro: FiltroPersonas, paginacion: Paginacion) -> Pagina[Persona]: ...
    async def agregar(self, persona: Persona) -> Persona: ...
    async def agregar_muchas(self, personas: list[Persona]) -> int: ...
    async def actualizar(self, persona: Persona) -> Persona: ...
    async def eliminar(self, persona_id: UUID) -> None: ...
    async def existe_cedula(self, cedula: Cedula, *, excluyendo: UUID | None = None) -> bool: ...

    async def seleccionar_para_cobertura(
        self, *, desde: datetime, hasta: datetime, limite: int | None = None
    ) -> list[Persona]:
        """Personas activas sin consulta exitosa dentro del periodo dado.

        Es la consulta que materializa la regla de no repetir a nadie antes de
        cubrir a todos: quien ya fue consultado con exito en la ventana queda
        fuera del conjunto de candidatos.
        """
        ...

    async def contar_activas(self) -> int: ...


class RepositorioTitulos(Protocol):
    async def obtener(self, titulo_id: UUID) -> Titulo | None: ...
    async def listar(self, filtro: FiltroTitulos, paginacion: Paginacion) -> Pagina[Titulo]: ...
    async def listar_por_persona(
        self, persona_id: UUID, *, incluir_retirados: bool = True
    ) -> list[Titulo]: ...
    async def agregar(self, titulo: Titulo) -> Titulo: ...
    async def agregar_muchos(self, titulos: list[Titulo]) -> int: ...
    async def actualizar(self, titulo: Titulo) -> Titulo: ...
    async def actualizar_muchos(self, titulos: list[Titulo]) -> int: ...
    async def eliminar(self, titulo_id: UUID) -> None: ...
    async def contar_por_persona(self, persona_id: UUID) -> int: ...


class RepositorioLogsConsulta(Protocol):
    async def obtener(self, log_id: UUID) -> ConsultaLog | None: ...
    async def listar(self, filtro: FiltroLogs, paginacion: Paginacion) -> Pagina[ConsultaLog]: ...
    async def agregar(self, log: ConsultaLog) -> ConsultaLog: ...
    async def ultimo_de_persona(self, persona_id: UUID) -> ConsultaLog | None: ...
    async def contar_en_ventana(self, desde: datetime, hasta: datetime) -> int:
        """Consultas realizadas en la ventana. Alimenta el presupuesto horario."""
        ...


class RepositorioJobs(Protocol):
    async def obtener(self, job_id: UUID) -> JobCobertura | None: ...
    async def listar(
        self, paginacion: Paginacion, *, estado: EstadoJob | None = None
    ) -> Pagina[JobCobertura]: ...
    async def job_activo(self) -> JobCobertura | None:
        """Job en curso o pausado. Solo puede haber uno: dos campanas simultaneas
        romperian la garantia de cobertura del periodo."""
        ...

    async def agregar(self, job: JobCobertura) -> JobCobertura: ...
    async def actualizar(self, job: JobCobertura) -> JobCobertura: ...

    async def agregar_items(self, items: list[ItemJob]) -> int: ...
    async def obtener_item(self, item_id: UUID) -> ItemJob | None: ...
    async def obtener_item_por_desafio(self, desafio_id: str) -> ItemJob | None: ...
    async def siguiente_item(self, job_id: UUID, *, ahora: datetime) -> ItemJob | None:
        """Reclama el siguiente item listo. La implementacion debe bloquear la
        fila (`FOR UPDATE SKIP LOCKED`) para que dos trabajadores no tomen la
        misma persona."""
        ...

    async def actualizar_item(self, item: ItemJob) -> ItemJob: ...
    async def listar_items(
        self, job_id: UUID, paginacion: Paginacion, *, estado: str | None = None
    ) -> Pagina[ItemJob]: ...
    async def contar_items_pendientes(self, job_id: UUID) -> int: ...
