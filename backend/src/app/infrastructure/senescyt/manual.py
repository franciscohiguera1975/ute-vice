"""Proveedor asistido: la verificacion la resuelve una persona.

## Que hace y que no

El portal publico de consulta de titulos protege sus busquedas con un desafio de
verificacion. Este adaptador **no lo resuelve**: lo captura, se lo presenta a un
operador en la interfaz web, y reanuda la consulta con la respuesta que esa
persona escribio. Un humano resuelve el desafio, que es exactamente para lo que
el desafio existe.

Lo que este modulo deliberadamente **no** incluye:

* reconocimiento automatico de imagenes ni servicios de resolucion de captcha;
* rotacion de direcciones de salida, proxies o VPN;
* suplantacion de identificadores de cliente para evitar ser reconocido como
  automatizacion.

El adaptador se identifica siempre mediante `User-Agent` y `From`, y ante un
rechazo del proveedor (429 o 403) devuelve `RECHAZADO`, lo que detiene el job a
traves del cortacircuitos en lugar de insistir.

## Configuracion obligatoria

Los detalles del formulario del portal (rutas, nombres de campo, selectores) no
vienen fijados en el codigo: cambian cuando el portal cambia, y codificarlos a
ciegas produciria un adaptador que falla en silencio. Se declaran en
`ConfiguracionPortal` y **deben verificarse contra el portal real antes de
habilitar este proveedor**. Sin configuracion, `verificar_disponibilidad()`
devuelve `False` y el job se niega a arrancar.

Ver `docs/manual/consultas-senescyt.md` para el procedimiento de puesta a punto.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx

from app.core.logging import get_logger
from app.domain.ports.senescyt import (
    DesafioVerificacion,
    ResultadoConsulta,
    TituloExterno,
)
from app.domain.value_objects import Cedula

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ConfiguracionPortal:
    """Contrato con el portal. Debe verificarse contra el sitio real.

    Se deja vacio por defecto a proposito: un adaptador con rutas inventadas
    daria la falsa impresion de estar operativo.
    """

    url_formulario: str = ""
    """Pagina que inicia la consulta y entrega el desafio."""

    url_consulta: str = ""
    """Endpoint que recibe la cedula y la respuesta al desafio."""

    campo_cedula: str = ""
    campo_respuesta_desafio: str = ""
    campo_token_formulario: str = ""

    ruta_imagen_desafio: str = ""
    """Ruta relativa de la imagen del desafio dentro de la pagina."""

    contacto_institucional: str = ""
    """Correo con el que el sistema se identifica en cada peticion."""

    @property
    def esta_configurado(self) -> bool:
        return bool(
            self.url_formulario
            and self.url_consulta
            and self.campo_cedula
            and self.campo_respuesta_desafio
        )


@dataclass(slots=True)
class _SesionDesafio:
    """Estado de una consulta que quedo esperando respuesta humana."""

    cedula: str
    cookies: dict[str, str] = field(default_factory=dict)
    token_formulario: str = ""
    creado_en: float = 0.0


class ProveedorManual:
    """Implementacion del puerto `ProveedorConsultaTitulos` con operador humano.

    Flujo:

    1. `consultar()` abre la pagina, obtiene el desafio y lo devuelve como
       `DesafioVerificacion` con la imagen en base64. La consulta queda en
       espera y el item del job pasa a `ESPERANDO_DESAFIO`.
    2. Un operador con permiso `consultas:resolver` ve el desafio en la interfaz
       y escribe la respuesta.
    3. `resolver_desafio()` reenvia el formulario con esa respuesta y devuelve
       los titulos.

    La sesion HTTP se conserva entre ambos pasos: sin las mismas cookies, el
    portal considera la respuesta como perteneciente a otra sesion.
    """

    def __init__(
        self,
        config: ConfiguracionPortal,
        *,
        base_url: str,
        timeout_segundos: int = 30,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self._cfg = config
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_segundos
        self._cliente = cliente
        self._sesiones: dict[str, _SesionDesafio] = {}

    @property
    def nombre(self) -> str:
        return "senescyt-manual"

    @property
    def requiere_verificacion_humana(self) -> bool:
        return True

    # ------------------------------------------------------------ cabeceras
    def _cabeceras(self) -> dict[str, str]:
        """Identificacion honesta del cliente.

        El sistema se presenta como lo que es: un proceso institucional de la
        UTE, con un contacto al que escribir. Si el proveedor quiere limitar o
        bloquear este trafico, tiene toda la informacion para hacerlo — que es
        precisamente como debe funcionar.
        """
        cabeceras = {
            "User-Agent": (
                "UTE-Vice/1.0 (validacion de titulos del personal; "
                "Universidad Tecnologica Equinoccial)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-EC,es;q=0.9",
        }
        if self._cfg.contacto_institucional:
            cabeceras["From"] = self._cfg.contacto_institucional
        return cabeceras

    async def _obtener_cliente(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._cabeceras(),
                follow_redirects=True,
            )
        return self._cliente

    # ------------------------------------------------------------- consulta
    async def consultar(self, cedula: Cedula) -> ResultadoConsulta:
        if not self._cfg.esta_configurado:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=(
                    "El proveedor manual no esta configurado. Complete "
                    "`ConfiguracionPortal` con los datos verificados del portal "
                    "antes de habilitarlo. Ver docs/manual/consultas-senescyt.md"
                ),
                codigo_http=None,
            )

        cliente = await self._obtener_cliente()
        try:
            respuesta = await cliente.get(self._cfg.url_formulario)
        except httpx.TimeoutException:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje="Tiempo de espera agotado al abrir el formulario",
                codigo_http=None,
            )
        except httpx.HTTPError as exc:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=f"Error de red: {exc}",
                codigo_http=None,
            )

        if respuesta.status_code in {403, 429}:
            # El proveedor nos esta limitando. Se respeta: se informa como
            # rechazo, lo que abre el cortacircuitos y detiene el job.
            log.warning(
                "El proveedor rechazo la peticion; el job se detendra",
                extra={"estado": respuesta.status_code},
            )
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=(
                    f"El proveedor rechazo la peticion (HTTP {respuesta.status_code}). "
                    "El proceso se detiene hasta revision manual."
                ),
                codigo_http=respuesta.status_code,
            )

        if respuesta.status_code != 200:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=f"Respuesta inesperada del portal (HTTP {respuesta.status_code})",
                codigo_http=respuesta.status_code,
            )

        imagen, token = await self._extraer_desafio(cliente, respuesta.text)

        desafio_id = f"sen-{uuid4().hex}"
        self._sesiones[desafio_id] = _SesionDesafio(
            cedula=cedula.valor,
            cookies=dict(cliente.cookies),
            token_formulario=token,
        )

        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=False,
            desafio=DesafioVerificacion(
                desafio_id=desafio_id,
                tipo="imagen",
                imagen_base64=imagen,
                instruccion="Transcriba el codigo que aparece en la imagen",
                expira_en_segundos=300,
                contexto={"cedula": cedula.valor, "token": token},
            ),
            mensaje="La consulta requiere verificacion humana",
        )

    async def resolver_desafio(
        self, desafio_id: str, respuesta: str, contexto: dict[str, Any]
    ) -> ResultadoConsulta:
        sesion = self._sesiones.pop(desafio_id, None)
        cedula_texto = sesion.cedula if sesion else str(contexto.get("cedula", ""))

        if not cedula_texto:
            return ResultadoConsulta(
                cedula="",
                exitosa=False,
                mensaje=(
                    "La sesion del desafio expiro. El proceso reintentara la "
                    "consulta desde el inicio."
                ),
                codigo_http=410,
            )

        cliente = await self._obtener_cliente()
        formulario = {
            self._cfg.campo_cedula: cedula_texto,
            self._cfg.campo_respuesta_desafio: respuesta,
        }
        if self._cfg.campo_token_formulario and sesion:
            formulario[self._cfg.campo_token_formulario] = sesion.token_formulario

        try:
            resultado = await cliente.post(
                self._cfg.url_consulta,
                data=formulario,
                cookies=sesion.cookies if sesion else None,
            )
        except httpx.HTTPError as exc:
            return ResultadoConsulta(
                cedula=cedula_texto,
                exitosa=False,
                mensaje=f"Error de red al enviar la respuesta: {exc}",
                codigo_http=None,
            )

        if resultado.status_code in {403, 429}:
            return ResultadoConsulta(
                cedula=cedula_texto,
                exitosa=False,
                mensaje=f"El proveedor rechazo la peticion (HTTP {resultado.status_code})",
                codigo_http=resultado.status_code,
            )
        if resultado.status_code != 200:
            return ResultadoConsulta(
                cedula=cedula_texto,
                exitosa=False,
                mensaje=f"Respuesta inesperada (HTTP {resultado.status_code})",
                codigo_http=resultado.status_code,
            )

        return self._interpretar_resultado(cedula_texto, resultado.text)

    async def verificar_disponibilidad(self) -> bool:
        if not self._cfg.esta_configurado:
            log.error(
                "El proveedor manual esta seleccionado pero sin configurar. "
                "El job no arrancara. Ver docs/manual/consultas-senescyt.md"
            )
            return False
        try:
            cliente = await self._obtener_cliente()
            respuesta = await cliente.get(self._cfg.url_formulario)
            return respuesta.status_code == 200
        except httpx.HTTPError:
            return False

    async def cerrar(self) -> None:
        self._sesiones.clear()
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    # ------------------------------------------------------------ internos
    async def _extraer_desafio(
        self, cliente: httpx.AsyncClient, html: str
    ) -> tuple[str | None, str]:
        """Obtiene la imagen del desafio y el token del formulario.

        La extraccion depende de la estructura real del portal. Se implementa
        contra `ConfiguracionPortal.ruta_imagen_desafio`, que el operador ajusta
        tras inspeccionar el sitio.
        """
        token = ""
        if self._cfg.campo_token_formulario:
            token = _extraer_valor_input(html, self._cfg.campo_token_formulario)

        if not self._cfg.ruta_imagen_desafio:
            return None, token

        try:
            imagen = await cliente.get(self._cfg.ruta_imagen_desafio)
            if imagen.status_code == 200 and imagen.content:
                return base64.b64encode(imagen.content).decode("ascii"), token
        except httpx.HTTPError as exc:
            log.warning("No se pudo descargar la imagen del desafio: %s", exc)

        return None, token

    def _interpretar_resultado(self, cedula: str, html: str) -> ResultadoConsulta:
        """Convierte la respuesta del portal en titulos del dominio.

        El analisis concreto del HTML depende del portal y debe implementarse al
        configurar el adaptador. Mientras no este implementado, se devuelve un
        error explicito en lugar de un exito vacio: un "sin titulos" falso
        marcaria a la persona como consultada y la sacaria de la cola.
        """
        titulos = self._analizar_html(html)
        if titulos is None:
            return ResultadoConsulta(
                cedula=cedula,
                exitosa=False,
                mensaje=(
                    "El analisis de la respuesta del portal no esta implementado "
                    "para este proveedor. Implemente `_analizar_html` con la "
                    "estructura verificada del portal antes de usarlo en produccion."
                ),
                codigo_http=501,
                respuesta_cruda={"longitud_html": len(html)},
            )

        return ResultadoConsulta(
            cedula=cedula,
            exitosa=True,
            titulos=titulos,
            codigo_http=200,
            respuesta_cruda={"longitud_html": len(html)},
        )

    def _analizar_html(self, html: str) -> list[TituloExterno] | None:
        """Punto de extension: analisis del HTML de resultados.

        Devuelve `None` mientras no este implementado. Se deja explicito y no
        como una lista vacia porque significan cosas distintas: `None` es "no se
        pudo leer", `[]` es "la persona no tiene titulos".
        """
        return None


def _extraer_valor_input(html: str, nombre_campo: str) -> str:
    """Lee el `value` de un `<input>` por su atributo `name`.

    Extraccion minima con expresion regular: suficiente para un token oculto y
    sin agregar una dependencia de analisis de HTML que solo se usaria aqui.
    """
    import re

    patron = re.compile(
        rf'<input[^>]*name=["\']{re.escape(nombre_campo)}["\'][^>]*value=["\']([^"\']*)["\']',
        re.IGNORECASE,
    )
    coincidencia = patron.search(html)
    return coincidencia.group(1) if coincidencia else ""
