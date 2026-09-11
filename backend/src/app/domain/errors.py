"""Errores del dominio.

La capa de dominio no conoce HTTP. Lanza estos errores; es la capa de API la
que los traduce a codigos de estado (ver `app/api/errors.py`). Asi el mismo caso
de uso sirve igual a un endpoint REST, a un comando de consola o —mas adelante—
a una herramienta invocada por un agente.
"""

from __future__ import annotations

from typing import Any


class ErrorDominio(Exception):
    """Raiz de la jerarquia. Todo error esperado del negocio hereda de aqui."""

    codigo: str = "error_dominio"
    mensaje_por_defecto: str = "Ocurrio un error de negocio"

    def __init__(
        self,
        mensaje: str | None = None,
        *,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        self.mensaje = mensaje or self.mensaje_por_defecto
        self.detalles = detalles or {}
        super().__init__(self.mensaje)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(codigo={self.codigo!r}, mensaje={self.mensaje!r})"


# ---------------------------------------------------------------------------
# Validacion y estado
# ---------------------------------------------------------------------------


class ErrorValidacion(ErrorDominio):
    """Un valor no cumple una regla de negocio."""

    codigo = "validacion"
    mensaje_por_defecto = "Los datos proporcionados no son validos"

    def __init__(
        self,
        mensaje: str | None = None,
        *,
        campo: str | None = None,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        detalles = dict(detalles or {})
        if campo:
            detalles["campo"] = campo
        super().__init__(mensaje, detalles=detalles)
        self.campo = campo


class NoEncontrado(ErrorDominio):
    """La entidad solicitada no existe."""

    codigo = "no_encontrado"
    mensaje_por_defecto = "El recurso solicitado no existe"

    def __init__(self, entidad: str, identificador: Any = None) -> None:
        mensaje = (
            f"{entidad} no encontrado"
            if identificador is None
            else f"{entidad} no encontrado: {identificador}"
        )
        super().__init__(mensaje, detalles={"entidad": entidad, "id": str(identificador)})


class YaExiste(ErrorDominio):
    """Violacion de una restriccion de unicidad del negocio."""

    codigo = "ya_existe"
    mensaje_por_defecto = "El recurso ya existe"

    def __init__(self, entidad: str, campo: str, valor: Any) -> None:
        super().__init__(
            f"Ya existe {entidad} con {campo} = {valor}",
            detalles={"entidad": entidad, "campo": campo, "valor": str(valor)},
        )


class ConflictoDeEstado(ErrorDominio):
    """La operacion es valida en si, pero no en el estado actual de la entidad.

    Ejemplo: reanudar un job que ya fue cancelado.
    """

    codigo = "conflicto_estado"
    mensaje_por_defecto = "La operacion no es valida en el estado actual"


class ReglaDeNegocioViolada(ErrorDominio):
    """Invariante del negocio que no encaja en las categorias anteriores."""

    codigo = "regla_negocio"
    mensaje_por_defecto = "La operacion viola una regla de negocio"


# ---------------------------------------------------------------------------
# Identidad y acceso
# ---------------------------------------------------------------------------


class ErrorAutenticacion(ErrorDominio):
    """Credenciales invalidas, ausentes o expiradas."""

    codigo = "no_autenticado"
    mensaje_por_defecto = "Credenciales invalidas"


class CredencialesInvalidas(ErrorAutenticacion):
    codigo = "credenciales_invalidas"
    mensaje_por_defecto = "Usuario o contrasena incorrectos"


class TokenInvalido(ErrorAutenticacion):
    codigo = "token_invalido"
    mensaje_por_defecto = "El token es invalido o ha expirado"


class UsuarioInactivo(ErrorAutenticacion):
    codigo = "usuario_inactivo"
    mensaje_por_defecto = "La cuenta esta desactivada"


class UsuarioBloqueado(ErrorAutenticacion):
    codigo = "usuario_bloqueado"
    mensaje_por_defecto = "La cuenta esta bloqueada temporalmente por intentos fallidos"

    def __init__(self, minutos_restantes: int) -> None:
        super().__init__(
            f"Cuenta bloqueada. Reintente en {minutos_restantes} minuto(s).",
            detalles={"minutos_restantes": minutos_restantes},
        )


class FueraDeAlcance(ErrorDominio):
    """El registro existe, pero no dentro de lo que esta cuenta puede consultar.

    Se distingue de `ErrorAutorizacion` a proposito: el permiso esta, lo que
    falta es la facultad o la carrera. Decirlo asi evita que alguien crea que le
    falta un rol cuando lo que le falta es alcance.
    """

    codigo = "fuera_de_alcance"
    mensaje_por_defecto = "El registro esta fuera de las facultades y carreras que puede consultar"

    def __init__(self, recurso: str = "registro") -> None:
        super().__init__(
            f"Este {recurso} pertenece a una facultad o carrera que no tiene asignada. "
            "Solicite que amplien su alcance si necesita consultarlo.",
            detalles={"recurso": recurso},
        )


class ErrorAutorizacion(ErrorDominio):
    """Autenticado, pero sin permiso para esta operacion."""

    codigo = "sin_permiso"
    mensaje_por_defecto = "No tiene permiso para realizar esta operacion"

    def __init__(self, permiso_requerido: str | None = None) -> None:
        mensaje = (
            self.mensaje_por_defecto
            if permiso_requerido is None
            else f"Se requiere el permiso '{permiso_requerido}'"
        )
        super().__init__(mensaje, detalles={"permiso_requerido": permiso_requerido})


class ProveedorNoHabilitado(ErrorDominio):
    """Se intento usar un metodo de acceso deshabilitado en la configuracion."""

    codigo = "proveedor_no_habilitado"

    def __init__(self, proveedor: str) -> None:
        super().__init__(
            f"El metodo de acceso '{proveedor}' no esta habilitado en esta instalacion",
            detalles={"proveedor": proveedor},
        )


# ---------------------------------------------------------------------------
# Consultas externas
# ---------------------------------------------------------------------------


class ErrorProveedorExterno(ErrorDominio):
    """Fallo al consultar un sistema externo. Se registra en el historico."""

    codigo = "error_proveedor"
    mensaje_por_defecto = "El proveedor externo no respondio correctamente"

    def __init__(
        self,
        mensaje: str | None = None,
        *,
        proveedor: str = "desconocido",
        reintentable: bool = True,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        detalles = dict(detalles or {})
        detalles["proveedor"] = proveedor
        super().__init__(mensaje, detalles=detalles)
        self.proveedor = proveedor
        self.reintentable = reintentable


class DesafioRequerido(ErrorProveedorExterno):
    """El proveedor exige una verificacion que solo una persona puede resolver.

    No es un fallo: es el camino previsto. El caso de uso encola el desafio y
    un operador lo resuelve desde la interfaz.
    """

    codigo = "desafio_requerido"
    mensaje_por_defecto = "El proveedor requiere verificacion humana"

    def __init__(
        self,
        *,
        proveedor: str = "senescyt",
        desafio_id: str | None = None,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        detalles = dict(detalles or {})
        if desafio_id:
            detalles["desafio_id"] = desafio_id
        super().__init__(
            proveedor=proveedor,
            reintentable=False,
            detalles=detalles,
        )
        self.desafio_id = desafio_id


class LimiteDeConsultasAlcanzado(ErrorDominio):
    """Se agoto el presupuesto de peticiones de la ventana actual.

    Es un mecanismo propio de autocontencion, no una respuesta del proveedor.
    """

    codigo = "limite_consultas"
    mensaje_por_defecto = "Se alcanzo el limite de consultas configurado para esta ventana"

    def __init__(self, *, reintentar_en_segundos: int | None = None) -> None:
        super().__init__(detalles={"reintentar_en_segundos": reintentar_en_segundos})
        self.reintentar_en_segundos = reintentar_en_segundos


class FueraDeVentanaOperativa(ErrorDominio):
    """La hora actual esta fuera de las franjas configuradas para consultar."""

    codigo = "fuera_de_ventana"
    mensaje_por_defecto = "Fuera del horario configurado para ejecutar consultas"


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------


class ErrorGeneracionReporte(ErrorDominio):
    codigo = "error_reporte"
    mensaje_por_defecto = "No fue posible generar el reporte"


class ReporteDemasiadoAncho(ErrorGeneracionReporte):
    """El reporte tiene mas columnas de las que caben en una pagina.

    No es un fallo: una tabla de setenta columnas no es un documento
    imprimible. Se dice con claridad y se ofrece la alternativa, en lugar de
    dejar que el generador reviente a mitad del armado.
    """

    codigo = "reporte_demasiado_ancho"

    def __init__(self, columnas: int, maximo: int) -> None:
        super().__init__(
            f"El reporte tiene {columnas} columnas y en PDF caben {maximo}. "
            "Use Excel o CSV, o elija una plantilla con menos columnas.",
            detalles={"columnas": columnas, "maximo": maximo},
        )


class ReporteDemasiadoGrande(ErrorGeneracionReporte):
    codigo = "reporte_demasiado_grande"

    def __init__(self, filas: int, maximo: int) -> None:
        super().__init__(
            f"El reporte tendria {filas:,} filas y el maximo permitido es {maximo:,}. "
            "Aplique filtros adicionales.",
            detalles={"filas": filas, "maximo": maximo},
        )
