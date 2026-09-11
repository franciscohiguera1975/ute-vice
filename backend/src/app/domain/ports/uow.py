"""Puerto Unit of Work.

Un caso de uso que toca varias tablas necesita que todo se confirme o nada. En
lugar de que cada uno maneje transacciones de SQLAlchemy —lo que ataria la capa
de aplicacion a la base de datos— se expone esta abstraccion: el caso de uso
declara el limite transaccional y la infraestructura decide como cumplirlo.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.domain.ports.distributivo import (
    RepositorioCatalogos,
    RepositorioDistributivo,
    RepositorioDocentes,
)
from app.domain.ports.repositorios import (
    RepositorioJobs,
    RepositorioLogsConsulta,
    RepositorioPersonas,
    RepositorioRoles,
    RepositorioTitulos,
    RepositorioTokensRefresco,
    RepositorioUsuarios,
)


class UnidadDeTrabajo(Protocol):
    """Agrupa repositorios bajo una misma transaccion.

    Uso:

        async with uow:
            persona = await uow.personas.obtener(pid)
            await uow.titulos.agregar(titulo)
            await uow.commit()

    Si el bloque sale por excepcion sin haber confirmado, se revierte todo.
    """

    usuarios: RepositorioUsuarios
    roles: RepositorioRoles
    tokens: RepositorioTokensRefresco
    personas: RepositorioPersonas
    titulos: RepositorioTitulos
    logs: RepositorioLogsConsulta
    jobs: RepositorioJobs

    # --- Distributivo docente ---
    catalogos: RepositorioCatalogos
    docentes: RepositorioDocentes
    distributivo: RepositorioDistributivo

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def flush(self) -> None:
        """Envia los cambios pendientes sin cerrar la transaccion.

        Necesario cuando un paso posterior requiere el identificador generado
        por la base para una fila recien insertada.
        """
        ...
