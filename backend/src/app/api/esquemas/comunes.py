"""Esquemas compartidos por todos los endpoints."""

from __future__ import annotations

from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ports.repositorios import Pagina, Paginacion

T = TypeVar("T")


class EsquemaBase(BaseModel):
    """Base de todos los esquemas de salida."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RespuestaPaginada(EsquemaBase, Generic[T]):
    """Envoltura uniforme de los listados.

    El frontend implementa la paginacion una sola vez contra este contrato, en
    lugar de una por cada recurso.
    """

    items: list[T]
    total: int = Field(description="Total de registros que cumplen el filtro")
    pagina: int
    tamano: int
    total_paginas: int
    tiene_siguiente: bool
    tiene_anterior: bool

    @classmethod
    def desde(cls, pagina: Pagina[Any], items: list[T]) -> RespuestaPaginada[T]:
        return cls(
            items=items,
            total=pagina.total,
            pagina=pagina.pagina,
            tamano=pagina.tamano,
            total_paginas=pagina.total_paginas,
            tiene_siguiente=pagina.tiene_siguiente,
            tiene_anterior=pagina.tiene_anterior,
        )


class ParametrosPaginacion(BaseModel):
    """Parametros de paginacion recibidos por query string."""

    pagina: Annotated[int, Field(ge=1, description="Numero de pagina, desde 1")] = 1
    tamano: Annotated[int, Field(ge=1, le=200, description="Registros por pagina")] = 25
    ordenar_por: str | None = Field(default=None, description="Campo por el que ordenar")
    descendente: bool = Field(default=False, description="Orden descendente")

    def a_dominio(self) -> Paginacion:
        return Paginacion(
            pagina=self.pagina,
            tamano=self.tamano,
            ordenar_por=self.ordenar_por,
            descendente=self.descendente,
        )


class RespuestaError(EsquemaBase):
    """Forma unica de todos los errores de la API."""

    codigo: str = Field(description="Codigo estable del error, apto para logica")
    mensaje: str = Field(description="Descripcion legible para el usuario")
    detalles: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(
        default=None, description="Identificador de la peticion, para soporte"
    )


class RespuestaMensaje(EsquemaBase):
    """Confirmacion simple de una operacion sin cuerpo de retorno."""

    mensaje: str
    exito: bool = True


class EstadoSalud(EsquemaBase):
    estado: str
    version: str
    entorno: str
    base_datos: str
    proveedor_senescyt: str
    planificador_activo: bool
