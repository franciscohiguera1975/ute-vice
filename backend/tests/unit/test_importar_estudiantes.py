"""Pruebas de la importacion de matricula estudiantil.

Dobles en memoria, igual que en `test_importar_distributivo.py`: sin Excel,
sin base de datos y sin red.
"""

from __future__ import annotations

import pytest

from app.application.base import ContextoEjecucion
from app.application.casos_uso.importar_estudiantes import (
    EntradaImportacionEstudiantes,
    ImportarEstudiantes,
)
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.ports.importacion_estudiantes import BecaCruda, FilaCrudaEstudiante

pytestmark = pytest.mark.unit


def cruda(
    numero: int = 2,
    cedula: str = "1710034065",
    periodo: str = "262651",
    carrera: str | None = "MEDICINA",
    sede: str | None = "SEDE QUITO",
    **extra: object,
) -> FilaCrudaEstudiante:
    return FilaCrudaEstudiante(
        numero_fila=numero,
        periodo=periodo,
        cedula=cedula,
        sede=sede,
        facultad="CIENCIAS DE LA SALUD EUGENIO ESPEJO",
        carrera=carrera,
        tipo_carrera="VIGENTE",
        modalidad="PRESENCIAL",
        nivel_formacion_1="01 TERCER NIVEL",
        nivel_formacion_2="GRADO",
        id_banner="000106978",
        nombre="YEPEZ CARRANZA DYLAN ALFONSO",
        genero="MASCULINO",
        mail_personal="dylanalf13@gmail.com",
        mail_ute="dylan.yepez@ute.edu.ec",
        telefono_celular="0984741151",
        telefono_fijo=None,
        fecha_nacimiento=None,
        tipo_estudiante="ANTIGUO",
        sistema="BANNER",
        matriculado="MATRICULADO",
        solicitud_retiro=None,
        bloqueo_plataforma=False,
        estado="MA",
        **extra,  # type: ignore[arg-type]
    )


async def importar(uow, filas: list[FilaCrudaEstudiante]):  # type: ignore[no-untyped-def]
    caso = ImportarEstudiantes(uow)
    return await caso(
        EntradaImportacionEstudiantes(filas=tuple(filas)), ContextoEjecucion.sistema()
    )


async def _sembrar_carrera(uow, nombre: str = "MEDICINA") -> ElementoCatalogo:
    elemento = ElementoCatalogo(tipo=TipoCatalogo.CARRERA, codigo=nombre, nombre=nombre)
    return await uow.catalogos.agregar(elemento)


class TestCargaBasica:
    async def test_crea_estudiante_y_matricula(self, uow) -> None:
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(uow, [cruda()])

        assert resultado.estudiantes_creados == 1
        assert resultado.matriculas_creadas == 1
        assert resultado.sin_carrera_reconocida == 0
        assert resultado.exitosa

        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert matricula.carrera_id is not None
        assert matricula.periodo == "262651"

        estudiante = next(iter(uow.estudiantes.estudiantes.values()))
        assert estudiante.cedula == "1710034065"
        assert estudiante.genero_id is not None

    async def test_doble_matricula_comparte_el_mismo_estudiante(self, uow) -> None:
        """Una cedula repetida en el mismo periodo -distinta carrera o sede-
        es un solo estudiante con dos matriculas, no dos personas."""
        await _sembrar_carrera(uow, "MEDICINA")
        await _sembrar_carrera(uow, "ODONTOLOGIA")

        resultado = await importar(
            uow,
            [
                cruda(numero=2, carrera="MEDICINA", sede="SEDE QUITO"),
                cruda(numero=3, carrera="ODONTOLOGIA", sede="SEDE SANTO DOMINGO"),
            ],
        )

        assert resultado.estudiantes_creados == 1
        assert resultado.matriculas_creadas == 2
        assert len(uow.estudiantes.estudiantes) == 1
        assert len(uow.estudiantes.matriculas) == 2

    async def test_fusiona_filas_que_repiten_la_misma_matricula(self, uow) -> None:
        """Dos filas con la misma clave natural -estudiante, periodo,
        carrera y sede- no son una doble matricula -esa exige carrera o
        sede distinta-: en produccion resultaron ser la misma matricula con
        dos becas, cada una en su propia fila en lugar de concatenadas en la
        misma celda. Sin fusionarlas, el upsert por lote le pedia a Postgres
        actualizar la misma fila dos veces en una sola sentencia y
        `ON CONFLICT DO UPDATE` lo rechazaba con `CardinalityViolationError`.
        """
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(
            uow,
            [
                cruda(
                    numero=2,
                    becas=(BecaCruda(codigo_beca="B1", tipo_beca="DEPORTIVA", porcentaje="50"),),
                ),
                cruda(
                    numero=3,
                    becas=(BecaCruda(codigo_beca="B2", tipo_beca="HERMANO", porcentaje="10"),),
                ),
            ],
        )

        assert resultado.matriculas_creadas == 1
        assert resultado.filas_combinadas_por_duplicado == 1
        assert resultado.becas_creadas == 2
        assert len(uow.estudiantes.matriculas) == 1

        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert {b.codigo_beca for b in matricula.becas} == {"B1", "B2"}

    async def test_reutiliza_el_estudiante_ya_registrado(self, uow) -> None:
        await _sembrar_carrera(uow, "MEDICINA")
        await importar(uow, [cruda(numero=2, periodo="262651")])

        resultado = await importar(uow, [cruda(numero=3, periodo="262751")])

        assert resultado.estudiantes_creados == 0
        assert resultado.estudiantes_existentes == 1
        assert len(uow.estudiantes.estudiantes) == 1
        assert len(uow.estudiantes.matriculas) == 2


class TestCarreraNoReconocida:
    async def test_carrera_sin_coincidencia_queda_sin_id_y_se_cuenta(self, uow) -> None:
        # No se siembra ninguna carrera: nada puede coincidir.
        resultado = await importar(uow, [cruda(carrera="CARRERA QUE NO EXISTE")])

        assert resultado.sin_carrera_reconocida == 1
        # La fila no se rechaza ni se crea una carrera nueva.
        assert resultado.matriculas_creadas == 1
        assert resultado.exitosa
        assert len(await uow.catalogos.listar_todos(TipoCatalogo.CARRERA)) == 0

        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert matricula.carrera_id is None
        assert matricula.carrera == "CARRERA QUE NO EXISTE"

    async def test_el_match_es_por_igualdad_exacta_no_difusa(self, uow) -> None:
        """Un nombre parecido pero no identico no debe coincidir: el negocio
        exige igualdad exacta, nunca similitud por texto."""
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(uow, [cruda(carrera="MEDICINA VETERINARIA")])

        assert resultado.sin_carrera_reconocida == 1
        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert matricula.carrera_id is None


class TestBecasMultiples:
    async def test_separa_las_becas_por_posicion(self, uow) -> None:
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(
            uow,
            [
                cruda(
                    becas=(
                        BecaCruda(
                            codigo_beca="10001",
                            financiamiento="UTE",
                            tipo_beca="DEPORTIVA",
                            porcentaje="50",
                        ),
                        BecaCruda(
                            codigo_beca="10002",
                            financiamiento="ESTADO",
                            tipo_beca="EXCELENCIA ACADEMICA",
                            porcentaje="100",
                        ),
                    )
                )
            ],
        )

        assert resultado.becas_creadas == 2
        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert len(matricula.becas) == 2
        assert {b.tipo_beca for b in matricula.becas} == {"DEPORTIVA", "EXCELENCIA ACADEMICA"}
        porcentajes = {b.codigo_beca: b.porcentaje for b in matricula.becas}
        assert porcentajes["10001"] == 50.0
        assert porcentajes["10002"] == 100.0

    async def test_sin_becas_no_crea_ninguna_fila(self, uow) -> None:
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(uow, [cruda(becas=())])

        assert resultado.becas_creadas == 0
        matricula = next(iter(uow.estudiantes.matriculas.values()))
        assert matricula.becas == []


class TestRechazos:
    async def test_fila_sin_cedula_se_rechaza_sin_abortar_la_carga(self, uow) -> None:
        await _sembrar_carrera(uow, "MEDICINA")

        resultado = await importar(
            uow,
            [
                cruda(numero=2, cedula="1710034065"),
                cruda(numero=3, cedula=""),
                cruda(numero=4, cedula="0926687856"),
            ],
        )

        assert resultado.matriculas_creadas == 2
        assert len(resultado.rechazadas) == 1
        assert resultado.rechazadas[0].numero_fila == 3
        assert not resultado.exitosa

    async def test_una_carga_vacia_se_rechaza(self, uow) -> None:
        from app.domain.errors import ErrorValidacion

        with pytest.raises(ErrorValidacion):
            await importar(uow, [])
