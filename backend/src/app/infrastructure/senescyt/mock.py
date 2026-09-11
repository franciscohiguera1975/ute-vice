"""Proveedor simulado. Desarrollo, demostraciones y pruebas automatizadas.

Genera resultados **deterministas** a partir de la cedula: la misma cedula
produce siempre los mismos titulos. Eso es lo que permite escribir pruebas del
reconciliador y del planificador sin depender de nada externo.

Tambien simula los caminos que importan: personas sin titulos, errores de red,
rechazos y desafios de verificacion. Un proveedor de pruebas que solo devuelve
exitos deja sin ejercitar justamente el codigo mas delicado.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from app.domain.ports.senescyt import (
    DesafioVerificacion,
    ResultadoConsulta,
    TituloExterno,
)
from app.domain.value_objects import Cedula

_INSTITUCIONES = (
    "UNIVERSIDAD TECNOLOGICA EQUINOCCIAL",
    "UNIVERSIDAD CENTRAL DEL ECUADOR",
    "ESCUELA POLITECNICA NACIONAL",
    "PONTIFICIA UNIVERSIDAD CATOLICA DEL ECUADOR",
    "UNIVERSIDAD SAN FRANCISCO DE QUITO",
    "UNIVERSIDAD DE LAS AMERICAS",
    "ESCUELA SUPERIOR POLITECNICA DEL LITORAL",
    "UNIVERSIDAD TECNICA PARTICULAR DE LOJA",
)

_TITULOS_TERCER_NIVEL = (
    ("INGENIERO EN SISTEMAS INFORMATICOS", "INGENIERIA, INDUSTRIA Y CONSTRUCCION"),
    ("LICENCIADO EN CIENCIAS DE LA EDUCACION", "EDUCACION"),
    ("INGENIERO COMERCIAL", "ADMINISTRACION"),
    ("ABOGADO DE LOS TRIBUNALES Y JUZGADOS DE LA REPUBLICA", "DERECHO"),
    ("MEDICO CIRUJANO", "SALUD Y BIENESTAR"),
    ("PSICOLOGO CLINICO", "SALUD Y BIENESTAR"),
    ("ECONOMISTA", "CIENCIAS SOCIALES"),
    ("ARQUITECTO", "INGENIERIA, INDUSTRIA Y CONSTRUCCION"),
    ("INGENIERO CIVIL", "INGENIERIA, INDUSTRIA Y CONSTRUCCION"),
    ("LICENCIADO EN COMUNICACION SOCIAL", "CIENCIAS SOCIALES"),
)

_POSGRADOS = (
    ("MAGISTER EN ADMINISTRACION DE EMPRESAS", "ADMINISTRACION"),
    ("MAGISTER EN EDUCACION SUPERIOR", "EDUCACION"),
    ("MAGISTER EN GERENCIA DE PROYECTOS", "ADMINISTRACION"),
    ("MAGISTER EN DERECHO CONSTITUCIONAL", "DERECHO"),
    ("MAGISTER EN SISTEMAS DE INFORMACION", "TECNOLOGIAS DE LA INFORMACION"),
    ("DOCTOR EN CIENCIAS DE LA EDUCACION (PHD)", "EDUCACION"),
    ("ESPECIALISTA EN MEDICINA INTERNA", "SALUD Y BIENESTAR"),
)


class ProveedorMock:
    """Implementacion del puerto `ProveedorConsultaTitulos` con datos ficticios."""

    def __init__(
        self,
        *,
        latencia_segundos: float = 0.15,
        probabilidad_sin_titulos: float = 0.12,
        probabilidad_error: float = 0.05,
        probabilidad_desafio: float = 0.0,
        semilla_global: int = 2026,
    ) -> None:
        self._latencia = latencia_segundos
        self._p_vacio = probabilidad_sin_titulos
        self._p_error = probabilidad_error
        self._p_desafio = probabilidad_desafio
        self._semilla = semilla_global
        self._desafios: dict[str, str] = {}
        """Desafios emitidos y pendientes: `desafio_id -> cedula`."""

    @property
    def nombre(self) -> str:
        return "mock"

    @property
    def requiere_verificacion_humana(self) -> bool:
        return self._p_desafio > 0

    async def consultar(self, cedula: Cedula) -> ResultadoConsulta:
        await asyncio.sleep(self._latencia)
        rng = self._generador(cedula)

        sorteo = rng.random()
        if sorteo < self._p_error:
            return self._simular_error(cedula, rng)
        if sorteo < self._p_error + self._p_desafio:
            return self._emitir_desafio(cedula)
        if sorteo < self._p_error + self._p_desafio + self._p_vacio:
            return ResultadoConsulta(
                cedula=cedula.valor,
                exitosa=True,
                titulos=[],
                mensaje="No se encontraron titulos registrados para la cedula consultada",
                codigo_http=200,
            )

        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=True,
            titulos=self._generar_titulos(cedula, rng),
            nombre_reportado=None,
            codigo_http=200,
            respuesta_cruda={"origen": "mock", "determinista": True},
        )

    async def resolver_desafio(
        self, desafio_id: str, respuesta: str, contexto: dict[str, Any]
    ) -> ResultadoConsulta:
        cedula_texto = self._desafios.pop(desafio_id, None) or contexto.get("cedula")
        if not cedula_texto:
            return ResultadoConsulta(
                cedula="",
                exitosa=False,
                mensaje="El desafio expiro o no corresponde a esta sesion",
                codigo_http=410,
            )

        # El mock acepta cualquier respuesta de 4 o mas caracteres. Sirve para
        # ejercitar el camino completo de la cola manual sin adivinanzas.
        if len(respuesta.strip()) < 4:
            return self._emitir_desafio(Cedula(str(cedula_texto)))

        cedula = Cedula(str(cedula_texto))
        rng = self._generador(cedula)
        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=True,
            titulos=self._generar_titulos(cedula, rng),
            codigo_http=200,
            respuesta_cruda={"origen": "mock", "desafio_resuelto": desafio_id},
        )

    async def verificar_disponibilidad(self) -> bool:
        return True

    async def cerrar(self) -> None:
        self._desafios.clear()

    # ------------------------------------------------------------ internos
    def _generador(self, cedula: Cedula) -> random.Random:
        """Semilla derivada de la cedula: mismo insumo, mismo resultado."""
        digest = hashlib.sha256(f"{self._semilla}:{cedula.valor}".encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _generar_titulos(self, cedula: Cedula, rng: random.Random) -> list[TituloExterno]:
        titulos: list[TituloExterno] = []

        pregrado, area = rng.choice(_TITULOS_TERCER_NIVEL)
        anio_pregrado = rng.randint(1995, 2019)
        titulos.append(
            self._construir(pregrado, area, "TERCER NIVEL", anio_pregrado, cedula, rng, 0)
        )

        # Cerca de la mitad del personal universitario tiene posgrado.
        if rng.random() < 0.45:
            posgrado, area_pg = rng.choice(_POSGRADOS)
            anio_posgrado = min(anio_pregrado + rng.randint(3, 12), 2025)
            tipo = "CUARTO NIVEL - DOCTORADO" if "DOCTOR" in posgrado else "CUARTO NIVEL"
            titulos.append(self._construir(posgrado, area_pg, tipo, anio_posgrado, cedula, rng, 1))

        return titulos

    def _construir(
        self,
        denominacion: str,
        area: str,
        tipo: str,
        anio: int,
        cedula: Cedula,
        rng: random.Random,
        indice: int,
    ) -> TituloExterno:
        fecha = date(anio, rng.randint(1, 12), rng.randint(1, 28))
        registro = f"{rng.randint(1000, 9999)}-{anio}-{rng.randint(100000, 999999)}"
        return TituloExterno(
            denominacion=denominacion,
            institucion=rng.choice(_INSTITUCIONES),
            tipo=tipo,
            numero_registro=registro,
            fecha_registro=fecha,
            area=area,
            observacion=None,
            pais="ECUADOR",
            datos_crudos={
                "fuente": "mock",
                "cedula": cedula.enmascarada(),
                "indice": indice,
                "fecha_graduacion": (fecha - timedelta(days=rng.randint(30, 400))).isoformat(),
            },
        )

    def _simular_error(self, cedula: Cedula, rng: random.Random) -> ResultadoConsulta:
        codigo, mensaje = rng.choice(
            [
                (503, "El servicio no esta disponible temporalmente"),
                (504, "Tiempo de espera agotado en el proveedor"),
                (429, "Se alcanzo el limite de consultas permitidas"),
                (500, "Error interno del proveedor"),
            ]
        )
        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=False,
            mensaje=f"[simulado] {mensaje}",
            codigo_http=codigo,
        )

    def _emitir_desafio(self, cedula: Cedula) -> ResultadoConsulta:
        desafio_id = f"mock-{uuid4().hex[:16]}"
        self._desafios[desafio_id] = cedula.valor
        return ResultadoConsulta(
            cedula=cedula.valor,
            exitosa=False,
            desafio=DesafioVerificacion(
                desafio_id=desafio_id,
                tipo="codigo_simulado",
                imagen_base64=None,
                instruccion=(
                    "Desafio simulado. Escriba cualquier texto de 4 o mas caracteres "
                    "para continuar."
                ),
                expira_en_segundos=300,
                contexto={"cedula": cedula.valor},
            ),
            mensaje="Se requiere verificacion humana",
        )
