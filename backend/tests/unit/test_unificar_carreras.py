"""Pruebas de la unificacion de carreras.

El catalogo acumulo variantes del mismo programa porque cada origen lo escribia
a su manera. Unificarlas no es un `UPDATE`: al reasignar, dos filas del mismo
docente que estaban en variantes distintas del mismo periodo pasan a compartir
la clave natural. Eso es lo que se prueba aqui.
"""

from __future__ import annotations

import pytest

from app.application.base import ContextoEjecucion
from app.application.casos_uso.importar_distributivo import (
    EntradaImportacion,
    ImportarDistributivo,
)
from app.application.casos_uso.unificar_carreras import (
    EntradaUnificarCarreras,
    UnificarCarreras,
)
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.errors import ErrorValidacion, NoEncontrado
from app.domain.ports.importacion import FilaCrudaDistributivo

pytestmark = pytest.mark.unit


def cruda(carrera: str, *, identificacion="1710034065", pao="2026-1", numero=2, **horas):  # type: ignore[no-untyped-def]
    return FilaCrudaDistributivo(
        numero_fila=numero,
        identificacion=identificacion,
        pao=pao,
        facultad="FCII",
        carrera=carrera,
        horas=horas or {"Da": 10.0},
    )


async def sembrar(uow, *filas):  # type: ignore[no-untyped-def]
    caso = ImportarDistributivo(uow)
    await caso(EntradaImportacion(filas=tuple(filas)), ContextoEjecucion.sistema())


async def unificar(uow, destino, *variantes):  # type: ignore[no-untyped-def]
    caso = UnificarCarreras(uow)
    return await caso(
        EntradaUnificarCarreras(destino=destino, variantes=tuple(variantes)),
        ContextoEjecucion.sistema(),
    )


async def carreras(uow):  # type: ignore[no-untyped-def]
    return sorted(c.codigo for c in await uow.catalogos.listar_todos(TipoCatalogo.CARRERA))


class TestReasignacion:
    async def test_las_filas_pasan_a_la_carrera_de_destino(self, uow) -> None:
        await sembrar(
            uow,
            cruda("INGENIERÍA MECATRÓNICA", numero=2),
            cruda("MECATRÓNICA", identificacion="0912345678", numero=3),
        )
        resultado = await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        assert resultado.filas_reasignadas == 1
        assert resultado.filas_fusionadas == 0
        assert await carreras(uow) == ["INGENIERÍA MECATRÓNICA"]
        assert len(uow.distributivo.datos) == 2

    async def test_la_variante_desaparece_del_catalogo(self, uow) -> None:
        await sembrar(
            uow,
            cruda("MECATRÓNICA"),
            cruda("INGENIERÍA MECATRÓNICA", numero=3, identificacion="0912345678"),
        )
        resultado = await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        assert resultado.variantes_retiradas == 1
        assert "MECATRÓNICA" not in await carreras(uow)


class TestFusionPorClaveRepetida:
    """El caso que impide resolverlo con un UPDATE."""

    async def test_suma_las_horas_cuando_la_clave_choca(self, uow) -> None:
        # El mismo docente, el mismo periodo, dos variantes de la misma carrera.
        await sembrar(
            uow,
            cruda("INGENIERÍA MECATRÓNICA", numero=2, Da=11.2),
            cruda("MECATRÓNICA", numero=3, Da=14.8),
        )
        resultado = await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        assert resultado.filas_fusionadas == 1
        assert len(uow.distributivo.datos) == 1
        fila = next(iter(uow.distributivo.datos.values()))
        assert fila.total_horas == pytest.approx(26.0)

    async def test_informa_cada_fusion(self, uow) -> None:
        await sembrar(
            uow,
            cruda("INGENIERÍA MECATRÓNICA", numero=2, Da=11.2),
            cruda("MECATRÓNICA", numero=3, Da=14.8),
        )
        resultado = await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        # Se informa una a una: sumar cargas es una decision revisable.
        assert len(resultado.fusiones) == 1
        assert resultado.fusiones[0].horas_resultantes == pytest.approx(26.0)

    async def test_no_fusiona_periodos_distintos(self, uow) -> None:
        await sembrar(
            uow,
            cruda("INGENIERÍA MECATRÓNICA", pao="2025-1", numero=2),
            cruda("MECATRÓNICA", pao="2026-1", numero=3),
        )
        resultado = await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        assert resultado.filas_fusionadas == 0
        assert len(uow.distributivo.datos) == 2

    async def test_conserva_la_fila_que_ya_estaba_en_el_destino(self, uow) -> None:
        await sembrar(
            uow,
            cruda("INGENIERÍA MECATRÓNICA", numero=2, Da=11.2),
            cruda("MECATRÓNICA", numero=3, Da=14.8),
        )
        destino = await uow.catalogos.obtener_por_codigo(
            TipoCatalogo.CARRERA, "INGENIERÍA MECATRÓNICA"
        )
        previa = next(f.id for f in uow.distributivo.datos.values() if f.carrera_id == destino.id)
        await unificar(uow, "INGENIERÍA MECATRÓNICA", "MECATRÓNICA")

        # Su identificador sobrevive, y con el las materias enlazadas.
        assert previa in uow.distributivo.datos


class TestValidaciones:
    async def test_el_destino_no_puede_estar_entre_las_variantes(self, uow) -> None:
        await sembrar(uow, cruda("MECATRÓNICA"))
        with pytest.raises(ErrorValidacion):
            await unificar(uow, "MECATRÓNICA", "MECATRÓNICA")

    async def test_exige_al_menos_una_variante(self, uow) -> None:
        await sembrar(uow, cruda("MECATRÓNICA"))
        with pytest.raises(ErrorValidacion):
            await unificar(uow, "MECATRÓNICA")

    async def test_falla_si_una_carrera_no_existe(self, uow) -> None:
        await sembrar(uow, cruda("MECATRÓNICA"))
        with pytest.raises(NoEncontrado):
            await unificar(uow, "MECATRÓNICA", "NO EXISTE")
