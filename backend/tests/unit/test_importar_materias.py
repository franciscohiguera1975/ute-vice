"""Pruebas de la carga de materias por docente.

El reporte de origen agrupa por docente y semestre; el distributivo, por docente,
periodo, carrera y sede. Esa diferencia de grano es el nucleo del caso de uso, y
lo que se prueba aqui: a que filas van a parar las materias cuando el origen no
dice a cual pertenecen.
"""

from __future__ import annotations

import pytest

from app.application.base import ContextoEjecucion
from app.application.casos_uso.importar_distributivo import (
    EntradaImportacion,
    ImportarDistributivo,
)
from app.application.casos_uso.importar_materias import (
    EntradaImportacionMaterias,
    ImportarMaterias,
    nivel_declarado,
    prefijo_de_semestre,
)
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.ports.importacion import FilaCrudaDistributivo, FilaCrudaMateria

pytestmark = pytest.mark.unit


def fila_distributivo(
    identificacion: str = "1710034065",
    pao: str = "2026-1",
    facultad: str = "FCSEE",
    carrera: str = "MEDICINA",
    nivel: str | None = None,
    numero: int = 2,
) -> FilaCrudaDistributivo:
    return FilaCrudaDistributivo(
        numero_fila=numero,
        identificacion=identificacion,
        pao=pao,
        facultad=facultad,
        carrera=carrera,
        nivel=nivel,
        horas={"Da": 8.0},
    )


def materia(
    identificacion: str = "1710034065",
    semestre: str = "2026-1",
    codigo_periodo: str = "261651",
    nombre: str = "ANATOMIA",
    numero: int = 2,
) -> FilaCrudaMateria:
    return FilaCrudaMateria(
        numero_fila=numero,
        semestre=semestre,
        codigo_periodo=codigo_periodo,
        identificacion=identificacion,
        nombre_docente="PEREZ JUAN",
        materia=nombre,
    )


async def sembrar(uow, filas: list[FilaCrudaDistributivo]) -> None:  # type: ignore[no-untyped-def]
    caso = ImportarDistributivo(uow)
    await caso(EntradaImportacion(filas=tuple(filas)), ContextoEjecucion.sistema())


async def importar(uow, filas: list[FilaCrudaMateria]):  # type: ignore[no-untyped-def]
    caso = ImportarMaterias(uow)
    return await caso(EntradaImportacionMaterias(filas=tuple(filas)), ContextoEjecucion.sistema())


async def materias_de(uow, indice: int = 0) -> list[str]:  # type: ignore[no-untyped-def]
    """Nombres de las asignaturas enlazadas a una fila, en su orden."""
    fila_id = sorted(uow.distributivo.datos)[indice]
    catalogo = uow.catalogos.datos[TipoCatalogo.ASIGNATURA]
    return [catalogo[a].codigo for a in uow.distributivo.asignaturas_enlazadas.get(fila_id, [])]


class TestUnionBasica:
    async def test_enlaza_la_materia_con_la_fila_del_docente(self, uow) -> None:
        await sembrar(uow, [fila_distributivo()])
        resultado = await importar(uow, [materia()])

        assert resultado.asignaturas_creadas == 1
        assert resultado.enlaces_creados == 1
        assert resultado.filas_enlazadas == 1
        assert await materias_de(uow) == ["ANATOMIA"]

    async def test_varias_materias_quedan_en_la_misma_fila_y_ordenadas(self, uow) -> None:
        await sembrar(uow, [fila_distributivo()])
        await importar(
            uow,
            [
                materia(nombre="FISIOLOGIA", numero=2),
                materia(nombre="ANATOMIA", numero=3),
                materia(nombre="BIOQUIMICA", numero=4),
            ],
        )
        # Alfabetico y no el del archivo: es el orden que sale en la celda del
        # reporte, y asi dos exportaciones del mismo periodo son comparables.
        assert await materias_de(uow) == ["ANATOMIA", "BIOQUIMICA", "FISIOLOGIA"]

    async def test_no_duplica_la_misma_materia_repetida_en_el_origen(self, uow) -> None:
        await sembrar(uow, [fila_distributivo()])
        resultado = await importar(
            uow, [materia(nombre="ANATOMIA", numero=2), materia(nombre="ANATOMIA", numero=3)]
        )
        assert resultado.enlaces_creados == 1
        assert await materias_de(uow) == ["ANATOMIA"]

    async def test_volver_a_cargar_no_acumula(self, uow) -> None:
        await sembrar(uow, [fila_distributivo()])
        await importar(uow, [materia(nombre="ANATOMIA")])
        await importar(uow, [materia(nombre="FISIOLOGIA")])
        # Reemplaza, no agrega: el segundo reporte es la verdad vigente.
        assert await materias_de(uow) == ["FISIOLOGIA"]


class TestRepartoEntreVariasFilas:
    """El origen no dice a que carrera pertenece cada materia."""

    async def test_van_a_todas_las_filas_del_docente_en_el_semestre(self, uow) -> None:
        await sembrar(
            uow,
            [
                fila_distributivo(carrera="MEDICINA", numero=2),
                fila_distributivo(carrera="ODONTOLOGIA", numero=3),
            ],
        )
        resultado = await importar(uow, [materia(nombre="ANATOMIA")])

        assert resultado.filas_enlazadas == 2
        assert await materias_de(uow, 0) == ["ANATOMIA"]
        assert await materias_de(uow, 1) == ["ANATOMIA"]

    async def test_el_nivel_del_codigo_acota_el_destino(self, uow) -> None:
        await sembrar(
            uow,
            [
                fila_distributivo(carrera="MEDICINA", nivel="GRADO", numero=2),
                fila_distributivo(carrera="MAESTRIA EN SALUD", nivel="POSGRADO", numero=3),
            ],
        )
        # `261751` es posgrado: la materia no debe tocar la fila de grado.
        resultado = await importar(uow, [materia(codigo_periodo="261751", nombre="EPIDEMIOLOGIA")])
        assert resultado.filas_enlazadas == 1

    async def test_si_el_nivel_no_acierta_ninguna_se_usan_todas(self, uow) -> None:
        await sembrar(uow, [fila_distributivo(nivel="GRADO")])
        # El origen dice posgrado y el distributivo grado. Perder la materia por
        # esa discrepancia seria peor que enlazarla donde el docente si consta.
        resultado = await importar(uow, [materia(codigo_periodo="261751")])
        assert resultado.filas_enlazadas == 1

    async def test_no_cruza_semestres(self, uow) -> None:
        await sembrar(uow, [fila_distributivo(pao="2025-1")])
        resultado = await importar(uow, [materia(semestre="2026-1")])

        assert resultado.filas_enlazadas == 0
        assert resultado.materias_sin_destino == 1


class TestLoQueNoSePuedeEnlazar:
    async def test_docente_sin_fila_en_el_distributivo(self, uow) -> None:
        await sembrar(uow, [fila_distributivo(identificacion="1710034065")])
        resultado = await importar(uow, [materia(identificacion="0912345678")])

        assert resultado.enlaces_creados == 0
        assert [a.identificacion for a in resultado.sin_destino] == ["0912345678"]
        assert resultado.sin_destino[0].materias == 1

    async def test_agrupa_el_aviso_por_docente_y_semestre(self, uow) -> None:
        resultado = await importar(
            uow,
            [
                materia(identificacion="0912345678", nombre="A", numero=2),
                materia(identificacion="0912345678", nombre="B", numero=3),
            ],
        )
        assert len(resultado.sin_destino) == 1
        assert resultado.sin_destino[0].materias == 2

    async def test_educacion_continua_no_es_un_semestre(self, uow) -> None:
        resultado = await importar(uow, [materia(semestre="2025", codigo_periodo="251001")])

        assert resultado.semestres_sin_periodo == {"2025": 1}
        assert resultado.sin_destino == []


class TestConversiones:
    @pytest.mark.parametrize(
        ("semestre", "esperado"),
        [("2026-1", "261"), ("2020-2", "202"), ("2025-1", "251"), ("2026", None), ("", None)],
    )
    def test_prefijo_de_semestre(self, semestre: str, esperado: str | None) -> None:
        assert prefijo_de_semestre(semestre) == esperado

    @pytest.mark.parametrize(
        ("codigo", "esperado"),
        [
            # El SICAF numera la tecnologia con 55 y el sistema con 15: se
            # admiten las dos para que el mismo reporte sirva con cualquiera.
            ("261551", "15"),
            ("261151", "15"),
            ("261651", "65"),
            ("261751", "75"),
            ("242650", "65"),
            ("251001", None),
            ("", None),
        ],
    )
    def test_nivel_declarado(self, codigo: str, esperado: str | None) -> None:
        assert nivel_declarado(codigo) == esperado


class TestCodocencia:
    """Una materia dictada por varios docentes llega con las cedulas unidas."""

    async def test_separa_las_cedulas_y_enlaza_a_cada_docente(self, uow) -> None:
        await sembrar(
            uow,
            [
                fila_distributivo(identificacion="1710034065", numero=2),
                fila_distributivo(identificacion="0912345678", numero=3),
            ],
        )
        resultado = await importar(
            uow,
            [
                FilaCrudaMateria(
                    numero_fila=2,
                    semestre="2026-1",
                    codigo_periodo="261651",
                    identificacion="1710034065; 0912345678",
                    nombre_docente="PEREZ JUAN; GOMEZ ANA",
                    materia="ANATOMIA",
                )
            ],
        )
        assert resultado.filas_enlazadas == 2
        assert await materias_de(uow, 0) == ["ANATOMIA"]
        assert await materias_de(uow, 1) == ["ANATOMIA"]

    async def test_la_misma_cedula_repetida_cuenta_una_vez(self, uow) -> None:
        await sembrar(uow, [fila_distributivo()])
        resultado = await importar(uow, [materia(identificacion="1710034065; 1710034065")])
        assert resultado.enlaces_creados == 1

    async def test_el_aviso_usa_el_primer_nombre(self, uow) -> None:
        resultado = await importar(
            uow,
            [
                FilaCrudaMateria(
                    numero_fila=2,
                    semestre="2026-1",
                    codigo_periodo="261651",
                    identificacion="0912345678; 0999999999",
                    nombre_docente="GOMEZ ANA; RUIZ LUIS",
                    materia="ANATOMIA",
                )
            ],
        )
        # Cada cedula se informa por separado, no la celda entera.
        assert sorted(a.identificacion for a in resultado.sin_destino) == [
            "0912345678",
            "0999999999",
        ]
        assert resultado.sin_destino[0].nombre_docente == "GOMEZ ANA"


class TestNombreLegible:
    """Los nombres del SICAF llegan en mayusculas y abreviados."""

    @pytest.mark.parametrize(
        ("origen", "esperado"),
        [
            # Los romanos se conservan: son el nivel de la asignatura y
            # `Iii` no se lee.
            ("CLINICA III", "Clinica III"),
            ("OCLUSIÓN Y ATM I", "Oclusión y Atm I"),
            ("ORTODONCIA BEE II", "Ortodoncia Bee II"),
            # El origen une el nivel con el tema por guion, sin espacios.
            ("ADULTO II-AZOTEMIA AGUDA", "Adulto II-Azotemia Aguda"),
            ("MAESTRÍA EN SALUD PÚBLICA", "Maestría en Salud Pública"),
            ("FCSEE", "FCSEE"),
        ],
    )
    def test_titulo_legible(self, origen: str, esperado: str) -> None:
        from app.application.casos_uso.importar_distributivo import _titulo_legible

        assert _titulo_legible(origen) == esperado
