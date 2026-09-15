"""Enumeraciones del dominio.

Se usa `StrEnum` para que el valor persistido y el valor serializado en JSON
sean el mismo texto legible, sin tablas de traduccion en los bordes.
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Identidad y acceso
# ---------------------------------------------------------------------------


class AuthProvider(StrEnum):
    """Origen de la identidad de un usuario."""

    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    LDAP = "LDAP"


class RolCodigo(StrEnum):
    """Roles del sistema. Se siembran al inicializar y no se borran."""

    ADMIN = "ADMIN"
    """Control total, incluida la gestion de usuarios y roles."""

    COORDINADOR = "COORDINADOR"
    """Gestiona personas y titulos, lanza consultas y emite reportes."""

    ANALISTA = "ANALISTA"
    """Edita titulos, resuelve consultas manuales y emite reportes."""

    CONSULTA = "CONSULTA"
    """Solo lectura. Rol por defecto de usuarios federados nuevos."""

    CONSULTA_DISTRIBUTIVO = "CONSULTA_DISTRIBUTIVO"
    """Solo lectura del distributivo y sus catalogos, con reportes.

    Mas estrecho que `CONSULTA`, no mas amplio: no ve personas, titulos ni
    consultas al SENESCYT. Es para quien revisa la carga docente y necesita
    emitir los archivos, sin acceso al resto del expediente de cada persona.
    """


class Permiso(StrEnum):
    """Permisos atomicos. La autorizacion se evalua siempre contra estos.

    Convencion: `recurso:accion`. Los roles son agrupaciones de permisos; el
    codigo nunca pregunta por el rol, solo por el permiso — asi agregar un rol
    nuevo no obliga a tocar ningun endpoint.
    """

    # Personas
    PERSONAS_LEER = "personas:leer"
    PERSONAS_ESCRIBIR = "personas:escribir"
    PERSONAS_ELIMINAR = "personas:eliminar"
    PERSONAS_IMPORTAR = "personas:importar"

    # Titulos
    TITULOS_LEER = "titulos:leer"
    TITULOS_ESCRIBIR = "titulos:escribir"
    TITULOS_ELIMINAR = "titulos:eliminar"
    TITULOS_VERIFICAR = "titulos:verificar"

    # Consultas al SENESCYT
    CONSULTAS_LEER = "consultas:leer"
    CONSULTAS_EJECUTAR = "consultas:ejecutar"
    CONSULTAS_RESOLVER = "consultas:resolver"
    """Resolver desafios de la cola manual (transcribir el codigo mostrado)."""
    CONSULTAS_ADMINISTRAR = "consultas:administrar"
    """Crear, pausar, reanudar y cancelar jobs de cobertura."""

    # Reportes y tablero
    REPORTES_GENERAR = "reportes:generar"
    DASHBOARD_VER = "dashboard:ver"

    # Distributivo docente
    DISTRIBUTIVO_LEER = "distributivo:leer"
    DISTRIBUTIVO_ESCRIBIR = "distributivo:escribir"
    DISTRIBUTIVO_ELIMINAR = "distributivo:eliminar"
    DISTRIBUTIVO_IMPORTAR = "distributivo:importar"

    # Catalogos del distributivo (PAO, facultad, carrera, sede, ...)
    CATALOGOS_LEER = "catalogos:leer"
    CATALOGOS_ESCRIBIR = "catalogos:escribir"

    # Administracion
    USUARIOS_LEER = "usuarios:leer"
    USUARIOS_ESCRIBIR = "usuarios:escribir"
    USUARIOS_ELIMINAR = "usuarios:eliminar"
    ROLES_ADMINISTRAR = "roles:administrar"
    AUDITORIA_LEER = "auditoria:leer"


#: Composicion de cada rol. Fuente de verdad para la siembra inicial.
PERMISOS_POR_ROL: dict[RolCodigo, frozenset[Permiso]] = {
    RolCodigo.ADMIN: frozenset(Permiso),
    RolCodigo.COORDINADOR: frozenset(
        {
            Permiso.PERSONAS_LEER,
            Permiso.PERSONAS_ESCRIBIR,
            Permiso.PERSONAS_IMPORTAR,
            Permiso.TITULOS_LEER,
            Permiso.TITULOS_ESCRIBIR,
            Permiso.TITULOS_VERIFICAR,
            Permiso.CONSULTAS_LEER,
            Permiso.CONSULTAS_EJECUTAR,
            Permiso.CONSULTAS_RESOLVER,
            Permiso.CONSULTAS_ADMINISTRAR,
            Permiso.DISTRIBUTIVO_LEER,
            Permiso.DISTRIBUTIVO_ESCRIBIR,
            Permiso.DISTRIBUTIVO_ELIMINAR,
            Permiso.DISTRIBUTIVO_IMPORTAR,
            Permiso.CATALOGOS_LEER,
            Permiso.CATALOGOS_ESCRIBIR,
            Permiso.REPORTES_GENERAR,
            Permiso.DASHBOARD_VER,
            Permiso.USUARIOS_LEER,
            Permiso.AUDITORIA_LEER,
        }
    ),
    RolCodigo.ANALISTA: frozenset(
        {
            Permiso.PERSONAS_LEER,
            Permiso.TITULOS_LEER,
            Permiso.TITULOS_ESCRIBIR,
            Permiso.TITULOS_VERIFICAR,
            Permiso.CONSULTAS_LEER,
            Permiso.CONSULTAS_EJECUTAR,
            Permiso.CONSULTAS_RESOLVER,
            Permiso.DISTRIBUTIVO_LEER,
            Permiso.DISTRIBUTIVO_ESCRIBIR,
            Permiso.CATALOGOS_LEER,
            Permiso.REPORTES_GENERAR,
            Permiso.DASHBOARD_VER,
        }
    ),
    #: Ni `DISTRIBUTIVO_ESCRIBIR` ni `CATALOGOS_ESCRIBIR`: sin ellos la interfaz
    #: oculta los botones de alta, edicion y borrado, y el backend rechaza la
    #: operacion aunque alguien llame al endpoint a mano. `REPORTES_GENERAR`
    #: habilita la pantalla de reportes y las tres descargas —xlsx, csv y pdf—,
    #: que salen del mismo caso de uso.
    RolCodigo.CONSULTA_DISTRIBUTIVO: frozenset(
        {
            Permiso.DISTRIBUTIVO_LEER,
            Permiso.CATALOGOS_LEER,
            Permiso.REPORTES_GENERAR,
        }
    ),
    RolCodigo.CONSULTA: frozenset(
        {
            Permiso.PERSONAS_LEER,
            Permiso.TITULOS_LEER,
            Permiso.CONSULTAS_LEER,
            Permiso.DASHBOARD_VER,
            Permiso.DISTRIBUTIVO_LEER,
            Permiso.CATALOGOS_LEER,
        }
    ),
}


# ---------------------------------------------------------------------------
# Personas y titulos
# ---------------------------------------------------------------------------


class TipoDocumento(StrEnum):
    CEDULA = "CEDULA"
    PASAPORTE = "PASAPORTE"
    RUC = "RUC"


class TipoVinculacion(StrEnum):
    DOCENTE = "DOCENTE"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    DIRECTIVO = "DIRECTIVO"
    SERVICIOS = "SERVICIOS"
    OTRO = "OTRO"


class NivelTitulo(StrEnum):
    """Niveles segun la nomenclatura del sistema de educacion superior."""

    TECNICO = "TECNICO"
    TECNOLOGICO = "TECNOLOGICO"
    TERCER_NIVEL = "TERCER_NIVEL"
    ESPECIALIZACION = "ESPECIALIZACION"
    MAESTRIA = "MAESTRIA"
    DOCTORADO = "DOCTORADO"
    NO_DETERMINADO = "NO_DETERMINADO"


class OrigenTitulo(StrEnum):
    """Como entro el registro al sistema. Determina su nivel de confianza."""

    SENESCYT = "SENESCYT"
    """Obtenido de una consulta al registro nacional."""

    MANUAL = "MANUAL"
    """Cargado por un funcionario a partir de documentacion fisica."""

    IMPORTACION = "IMPORTACION"
    """Cargado masivamente desde un archivo."""


class EstadoTitulo(StrEnum):
    VIGENTE = "VIGENTE"
    """Presente en la ultima consulta exitosa."""

    RETIRADO = "RETIRADO"
    """Estaba en consultas previas y desaparecio: exige revision humana."""

    POR_VERIFICAR = "POR_VERIFICAR"
    """Cargado manualmente y aun sin contraste contra el registro nacional."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


class EstadoConsulta(StrEnum):
    """Resultado de una consulta individual. Se persiste en `consulta_logs`."""

    EXITO = "EXITO"
    """El proveedor respondio y se procesaron los titulos."""

    SIN_DATOS = "SIN_DATOS"
    """El proveedor respondio, la persona no tiene titulos registrados."""

    DESAFIO_PENDIENTE = "DESAFIO_PENDIENTE"
    """Requiere intervencion humana; espera en la cola de resolucion."""

    ERROR_PROVEEDOR = "ERROR_PROVEEDOR"
    """Fallo del lado del proveedor (5xx, formato inesperado)."""

    ERROR_RED = "ERROR_RED"
    """Tiempo agotado o fallo de conectividad."""

    ERROR_DATOS = "ERROR_DATOS"
    """La cedula es invalida o el proveedor la rechazo."""

    RECHAZADO = "RECHAZADO"
    """El proveedor rechazo la peticion (limite alcanzado, acceso denegado).

    Dispara el retroceso exponencial y puede abrir el cortacircuitos.
    """

    CANCELADO = "CANCELADO"
    """La consulta se anulo antes de completarse."""

    @property
    def es_error(self) -> bool:
        return self in _ESTADOS_ERROR

    @property
    def cuenta_para_cortacircuitos(self) -> bool:
        """Solo los fallos atribuibles al proveedor abren el cortacircuitos.

        Una cedula invalida es culpa del dato, no del proveedor: no debe
        detener el job entero.
        """
        return self in {
            EstadoConsulta.ERROR_PROVEEDOR,
            EstadoConsulta.ERROR_RED,
            EstadoConsulta.RECHAZADO,
        }


_ESTADOS_ERROR = frozenset(
    {
        EstadoConsulta.ERROR_PROVEEDOR,
        EstadoConsulta.ERROR_RED,
        EstadoConsulta.ERROR_DATOS,
        EstadoConsulta.RECHAZADO,
    }
)


class TipoCambio(StrEnum):
    """Que cambio entre la consulta anterior y la actual."""

    SIN_CAMBIOS = "SIN_CAMBIOS"
    TITULO_NUEVO = "TITULO_NUEVO"
    TITULO_MODIFICADO = "TITULO_MODIFICADO"
    TITULO_RETIRADO = "TITULO_RETIRADO"
    PRIMERA_CONSULTA = "PRIMERA_CONSULTA"


class EstadoJob(StrEnum):
    """Ciclo de vida de un job de cobertura."""

    BORRADOR = "BORRADOR"
    PROGRAMADO = "PROGRAMADO"
    EN_CURSO = "EN_CURSO"
    PAUSADO = "PAUSADO"
    """Pausado a mano o por el cortacircuitos."""
    COMPLETADO = "COMPLETADO"
    CANCELADO = "CANCELADO"

    @property
    def es_terminal(self) -> bool:
        return self in {EstadoJob.COMPLETADO, EstadoJob.CANCELADO}

    @property
    def admite_procesamiento(self) -> bool:
        return self is EstadoJob.EN_CURSO


class EstadoItemJob(StrEnum):
    """Estado de una persona dentro de un job de cobertura."""

    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    ESPERANDO_DESAFIO = "ESPERANDO_DESAFIO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"
    OMITIDO = "OMITIDO"
    """Descartado por regla de negocio (persona inactiva, cedula invalida)."""

    @property
    def es_terminal(self) -> bool:
        return self in {
            EstadoItemJob.COMPLETADO,
            EstadoItemJob.FALLIDO,
            EstadoItemJob.OMITIDO,
        }


class FormatoReporte(StrEnum):
    XLSX = "XLSX"
    CSV = "CSV"
    PDF = "PDF"
