"""Proveedor por API institucional (bajo convenio).

Es la via correcta y la que el proyecto recomienda: un acuerdo formal con la
entidad que administra el registro, con credenciales propias, cuotas pactadas y
sin desafios de verificacion de por medio.

El adaptador esta escrito contra un contrato REST convencional (`GET
/titulos/{cedula}` con autenticacion por cabecera). Cuando se firme el convenio,
lo previsible es ajustar `_mapear_respuesta` al esquema real; el resto del
sistema no cambia, porque todo depende del puerto y no de esta clase.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from app.core.logging import get_logger
from app.domain.ports.senescyt import ResultadoConsulta, TituloExterno
from app.domain.value_objects import Cedula

log = get_logger(__name__)


class ProveedorOficial:
    """Implementacion del puerto `ProveedorConsultaTitulos` sobre API oficial."""

    def __init__(
        self,
        *,
        url_base: str,
        api_key: str,
        timeout_segundos: int = 30,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        if not url_base:
            raise ValueError("El proveedor oficial requiere SENESCYT_OFICIAL_API_URL")
        self._url = url_base.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_segundos
        self._cliente = cliente

    @property
    def nombre(self) -> str:
        return "senescyt-oficial"

    @property
    def requiere_verificacion_humana(self) -> bool:
        return False

    async def _obtener_cliente(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                base_url=self._url,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "User-Agent": "UTE-Vice/1.0 (convenio institucional)",
                },
            )
        return self._cliente

    async def consultar(self, cedula: Cedula) -> ResultadoConsulta:
        cliente = await self._obtener_cliente()
        try:
            respuesta = await cliente.get(f"/titulos/{cedula.valor}")
        except httpx.TimeoutException:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje="Tiempo de espera agotado",
                codigo_http=None,
            )
        except httpx.HTTPError as exc:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=f"Error de red: {exc}",
                codigo_http=None,
            )

        if respuesta.status_code == 404:
            # La API distingue "no existe la persona" de "no tiene titulos".
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=True,
                titulos=[],
                mensaje="Sin titulos registrados",
                codigo_http=404,
            )
        if respuesta.status_code == 429:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje="Cuota de consultas agotada segun el convenio",
                codigo_http=429,
            )
        if respuesta.status_code != 200:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje=f"Respuesta inesperada (HTTP {respuesta.status_code})",
                codigo_http=respuesta.status_code,
            )

        try:
            datos = respuesta.json()
        except ValueError:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=False,
                mensaje="La respuesta no es JSON valido",
                codigo_http=200,
            )

        return self._mapear_respuesta(cedula, datos)

    async def resolver_desafio(
        self, desafio_id: str, respuesta: str, contexto: dict[str, Any]
    ) -> ResultadoConsulta:
        # La API bajo convenio no emite desafios; el metodo existe solo para
        # cumplir el puerto.
        raise NotImplementedError("El proveedor oficial no emite desafios de verificacion")

    async def verificar_disponibilidad(self) -> bool:
        try:
            cliente = await self._obtener_cliente()
            respuesta = await cliente.get("/salud")
            return respuesta.status_code == 200
        except httpx.HTTPError:
            return False

    async def cerrar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    # ------------------------------------------------------------ internos
    def _mapear_respuesta(self, cedula: Cedula, datos: Any) -> ResultadoConsulta:
        """Traduce el esquema de la API al DTO del dominio.

        Se acepta tanto una lista directa como un objeto con clave `titulos`,
        que son las dos formas habituales.
        """
        crudos = datos.get("titulos", datos if isinstance(datos, list) else [])
        titulos = [self._mapear_titulo(t) for t in crudos if isinstance(t, dict)]

        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=True,
            titulos=titulos,
            nombre_reportado=datos.get("nombre") if isinstance(datos, dict) else None,
            codigo_http=200,
            respuesta_cruda=datos if isinstance(datos, dict) else {"items": len(titulos)},
        )

    @staticmethod
    def _mapear_titulo(crudo: dict[str, Any]) -> TituloExterno:
        return TituloExterno(
            denominacion=str(crudo.get("titulo") or crudo.get("denominacion") or ""),
            institucion=str(crudo.get("institucion") or crudo.get("universidad") or ""),
            tipo=crudo.get("tipo") or crudo.get("nivel"),
            numero_registro=crudo.get("numero_registro") or crudo.get("registro"),
            fecha_registro=_a_fecha(crudo.get("fecha_registro")),
            area=crudo.get("area") or crudo.get("area_conocimiento"),
            observacion=crudo.get("observacion"),
            pais=crudo.get("pais") or "ECUADOR",
            datos_crudos=crudo,
        )


def _a_fecha(valor: Any) -> date | None:
    """Acepta ISO, `dd/mm/yyyy` y `dd-mm-yyyy`, que es lo que suele llegar."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    log.debug("Formato de fecha no reconocido: %r", texto)
    return None
