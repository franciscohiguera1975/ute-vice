"""Unidad de trabajo sobre SQLAlchemy asincrono."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from app.infrastructure.db.repositorios.auth import (
    RepositorioRolesSQL,
    RepositorioTokensSQL,
    RepositorioUsuariosSQL,
)
from app.infrastructure.db.repositorios.distributivo import (
    RepositorioCatalogosSQL,
    RepositorioDistributivoSQL,
    RepositorioDocentesSQL,
)
from app.infrastructure.db.repositorios.nucleo import (
    RepositorioJobsSQL,
    RepositorioLogsSQL,
    RepositorioPersonasSQL,
    RepositorioTitulosSQL,
)


class UnidadDeTrabajoSQL:
    """Implementacion del puerto `UnidadDeTrabajo`.

    Los repositorios se crean al entrar en el contexto, todos sobre la misma
    sesion. Esa es la propiedad que hace que un caso de uso que escribe en
    `titulos`, `personas` y `consulta_logs` confirme las tres o ninguna.

    Es reentrante: si ya hay una sesion abierta, `__aenter__` la reutiliza en
    lugar de anidar. Eso permite que un caso de uso invoque a un colaborador que
    tambien abre el contexto sin abrir una transaccion paralela.
    """

    # Los repositorios se declaran con el tipo del **puerto**, no con el de la
    # implementacion. Sin esa anotacion, la clase no satisface el protocolo
    # `UnidadDeTrabajo`: los atributos de un Protocol son invariantes.
    usuarios: RepositorioUsuarios
    roles: RepositorioRoles
    tokens: RepositorioTokensRefresco
    personas: RepositorioPersonas
    titulos: RepositorioTitulos
    logs: RepositorioLogsConsulta
    jobs: RepositorioJobs
    catalogos: RepositorioCatalogos
    docentes: RepositorioDocentes
    distributivo: RepositorioDistributivo

    def __init__(self, fabrica: async_sessionmaker[AsyncSession]) -> None:
        self._fabrica = fabrica
        self._sesion: AsyncSession | None = None
        self._profundidad = 0

    async def __aenter__(self) -> Self:
        self._profundidad += 1
        if self._sesion is None:
            self._sesion = self._fabrica()
            self._construir_repositorios(self._sesion)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._profundidad -= 1
        if self._profundidad > 0:
            return

        sesion = self._sesion
        self._sesion = None
        if sesion is None:
            return
        try:
            if exc_type is not None:
                await sesion.rollback()
        finally:
            await sesion.close()

    def _construir_repositorios(self, sesion: AsyncSession) -> None:
        self.usuarios = RepositorioUsuariosSQL(sesion)
        self.roles = RepositorioRolesSQL(sesion)
        self.tokens = RepositorioTokensSQL(sesion)
        self.personas = RepositorioPersonasSQL(sesion)
        self.titulos = RepositorioTitulosSQL(sesion)
        self.logs = RepositorioLogsSQL(sesion)
        self.jobs = RepositorioJobsSQL(sesion)
        self.catalogos = RepositorioCatalogosSQL(sesion)
        self.docentes = RepositorioDocentesSQL(sesion)
        self.distributivo = RepositorioDistributivoSQL(sesion)

    @property
    def sesion(self) -> AsyncSession:
        if self._sesion is None:
            raise RuntimeError(
                "La unidad de trabajo se usa fuera de su contexto: "
                "envuelva la operacion en `async with uow:`"
            )
        return self._sesion

    async def commit(self) -> None:
        await self.sesion.commit()

    async def rollback(self) -> None:
        await self.sesion.rollback()

    async def flush(self) -> None:
        await self.sesion.flush()
