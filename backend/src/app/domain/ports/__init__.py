"""Puertos del dominio: contratos que la infraestructura debe satisfacer."""

from app.domain.ports.reloj import (
    AleatorioDelSistema,
    FuenteAleatoria,
    Reloj,
    RelojCongelado,
    RelojDelSistema,
)
from app.domain.ports.reportes import (
    ArchivoReporte,
    ColumnaReporte,
    ExportadorReporte,
    RegistroExportadores,
    TablaReporte,
)
from app.domain.ports.repositorios import (
    FiltroLogs,
    FiltroPersonas,
    FiltroTitulos,
    Pagina,
    Paginacion,
    RepositorioJobs,
    RepositorioLogsConsulta,
    RepositorioPersonas,
    RepositorioRoles,
    RepositorioTitulos,
    RepositorioTokensRefresco,
    RepositorioUsuarios,
)
from app.domain.ports.seguridad import (
    ContenidoToken,
    HasherContrasenas,
    IdentidadExterna,
    ParDeTokens,
    ProveedorIdentidad,
    ProveedorOAuth,
    ServicioTokens,
)
from app.domain.ports.senescyt import (
    DesafioVerificacion,
    ProveedorConsultaTitulos,
    ResultadoConsulta,
    TituloExterno,
)
from app.domain.ports.uow import UnidadDeTrabajo

__all__ = [
    "AleatorioDelSistema",
    "ArchivoReporte",
    "ColumnaReporte",
    "ContenidoToken",
    "DesafioVerificacion",
    "ExportadorReporte",
    "FiltroLogs",
    "FiltroPersonas",
    "FiltroTitulos",
    "FuenteAleatoria",
    "HasherContrasenas",
    "IdentidadExterna",
    "Pagina",
    "Paginacion",
    "ParDeTokens",
    "ProveedorConsultaTitulos",
    "ProveedorIdentidad",
    "ProveedorOAuth",
    "RegistroExportadores",
    "Reloj",
    "RelojCongelado",
    "RelojDelSistema",
    "RepositorioJobs",
    "RepositorioLogsConsulta",
    "RepositorioPersonas",
    "RepositorioRoles",
    "RepositorioTitulos",
    "RepositorioTokensRefresco",
    "RepositorioUsuarios",
    "ResultadoConsulta",
    "ServicioTokens",
    "TablaReporte",
    "TituloExterno",
    "UnidadDeTrabajo",
]
