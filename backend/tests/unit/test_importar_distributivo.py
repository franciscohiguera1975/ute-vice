"""Pruebas de la importacion del consolidado.

Se ejercita la normalizacion completa con dobles en memoria: sin Excel, sin base
de datos y sin red. Los criterios que se prueban aqui —unificar sedes, no
unificar facultades, separar titulos, consolidar claves repetidas— salieron de
contrastar el consolidado historico real, y una regresion en cualquiera de ellos
produce cifras que parecen correctas pero no lo son.
"""

from __future__ import annotations

import pytest

from app.application.base import ContextoEjecucion
from app.application.casos_uso.importar_distributivo import (
    ALIAS_GENERO,
    ALIAS_SEDE,
    EntradaImportacion,
    ImportarDistributivo,
)
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.ports.importacion import FilaCrudaDistributivo

pytestmark = pytest.mark.unit


def cruda(
    numero: int = 2,
    identificacion: str = "1710034065",
    pao: str = "2026-1",
    facultad: str = "FCSEE",
    carrera: str | None = "MEDICINA",
    **extra: object,
) -> FilaCrudaDistributivo:
    return FilaCrudaDistributivo(
        numero_fila=numero,
        identificacion=identificacion,
        pao=pao,
        facultad=facultad,
        carrera=carrera,
        **extra,  # type: ignore[arg-type]
    )


async def importar(uow, filas: list[FilaCrudaDistributivo]):  # type: ignore[no-untyped-def]
    caso = ImportarDistributivo(uow)
    return await caso(EntradaImportacion(filas=tuple(filas)), ContextoEjecucion.sistema())


class TestCargaBasica:
    async def test_crea_catalogos_docentes_y_filas(self, uow) -> None:
        resultado = await importar(uow, [cruda(horas={"Da": 9.0, "Db": 2.5})])

        assert resultado.filas_creadas == 1
        assert resultado.docentes_creados == 1
        assert resultado.exitosa

        fila = next(iter(uow.distributivo.datos.values()))
        assert fila.total_horas == 11.5

        paos = await uow.catalogos.listar_todos(TipoCatalogo.PAO)
        # El semestre del consolidado se convierte en el periodo academico que
        # le corresponde por facultad y nivel.
        assert [p.codigo for p in paos] == ["261651"]
        assert [p.nombre for p in paos] == ["2026-1 GRADO"]

    async def test_un_docente_con_varias_filas_se_crea_una_sola_vez(self, uow) -> None:
        resultado = await importar(
            uow,
            [
                cruda(numero=2, carrera="MEDICINA", nombre="PEREZ JUAN"),
                cruda(numero=3, carrera="ODONTOLOGIA", nombre="PEREZ JUAN"),
            ],
        )
        assert resultado.docentes_creados == 1
        assert resultado.filas_creadas == 2

    async def test_reutiliza_los_docentes_ya_registrados(self, uow) -> None:
        await importar(uow, [cruda(numero=2, pao="2025-1")])
        resultado = await importar(uow, [cruda(numero=3, pao="2026-1")])

        assert resultado.docentes_creados == 0
        assert resultado.docentes_existentes == 1
        assert len(uow.docentes.datos) == 1


class TestNormalizacionDeSedes:
    """Las sedes se unifican: el origen escribe la misma de varias formas."""

    @pytest.mark.parametrize(
        ("variante", "esperado"),
        [
            ("QUITO", "QUITO"),
            ("SEDE QUITO", "QUITO"),
            ("SANTO DOMINGO", "SANTO DOMINGO"),
            ("SEDE SANTO DOMINGO", "SANTO DOMINGO"),
            ("MON", "MON"),
            ("RHO", "MON"),
            ("RICARDO HIDALGO OTTOLENGHI", "MON"),
            ("CUENCA", "CUENCA"),
            ("CAMPUS CUENCA", "CUENCA"),
        ],
    )
    def test_el_mapa_de_alias_cubre_las_variantes_reales(
        self, variante: str, esperado: str
    ) -> None:
        assert ALIAS_SEDE[variante] == esperado

    async def test_las_variantes_terminan_en_una_sola_sede(self, uow) -> None:
        """`MON`, `RHO` y el nombre largo son el mismo campus."""
        await importar(
            uow,
            [
                cruda(numero=2, sede="MON", carrera="A"),
                cruda(numero=3, sede="RHO", carrera="B"),
                cruda(numero=4, sede="RICARDO HIDALGO OTTOLENGHI", carrera="C"),
            ],
        )
        sedes = await uow.catalogos.listar_todos(TipoCatalogo.SEDE)
        assert [s.codigo for s in sedes] == ["MON"]

        ids = {f.sede_id for f in uow.distributivo.datos.values()}
        assert len(ids) == 1, "las tres filas deben apuntar a la misma sede"

    async def test_quito_y_sede_quito_son_la_misma(self, uow) -> None:
        await importar(
            uow,
            [
                cruda(numero=2, sede="QUITO", carrera="A"),
                cruda(numero=3, sede="SEDE QUITO", carrera="B"),
            ],
        )
        assert len(await uow.catalogos.listar_todos(TipoCatalogo.SEDE)) == 1


class TestFacultadesNoSeUnifican:
    async def test_las_facultades_se_conservan_tal_cual(self, uow) -> None:
        """En 2026-1 desaparecen FO, FCIC, CEL y ETECH porque hubo una
        reestructuracion real de facultades, no un error de captura.
        Normalizarlas borraria ese hecho del historico."""
        await importar(
            uow,
            [
                cruda(numero=2, pao="2025-1", facultad="FO", carrera="ODONTOLOGIA"),
                cruda(numero=3, pao="2026-1", facultad="FCSEE", carrera="ODONTOLOGIA"),
            ],
        )
        facultades = {f.codigo for f in await uow.catalogos.listar_todos(TipoCatalogo.FACULTAD)}
        assert facultades == {"FO", "FCSEE"}


class TestNormalizacionDeGenero:
    @pytest.mark.parametrize(
        ("variante", "esperado"),
        [
            ("MASCULINO", "MASCULINO"),
            ("HOMBRE", "MASCULINO"),
            ("FEMENINO", "FEMENINO"),
            ("MUJER", "FEMENINO"),
        ],
    )
    def test_el_mapa_cubre_las_variantes_reales(self, variante: str, esperado: str) -> None:
        assert ALIAS_GENERO[variante] == esperado

    async def test_las_variantes_terminan_en_dos_generos(self, uow) -> None:
        await importar(
            uow,
            [
                cruda(numero=2, identificacion="1710034065", genero="MASCULINO"),
                cruda(numero=3, identificacion="0926687856", genero="HOMBRE"),
                cruda(numero=4, identificacion="1713175477", genero="MUJER"),
                cruda(numero=5, identificacion="1104537772", genero="Femenino"),
            ],
        )
        generos = {g.codigo for g in await uow.catalogos.listar_todos(TipoCatalogo.GENERO)}
        assert generos == {"MASCULINO", "FEMENINO"}


class TestTitulos:
    async def test_separa_los_titulos_concatenados(self, uow) -> None:
        await importar(
            uow,
            [cruda(titulo="ARQUITECTO & MAGISTER EN URBANISMO , DOCTOR EN CIENCIAS")],
        )
        titulos = await uow.catalogos.listar_todos(TipoCatalogo.TITULO_PROFESIONAL)
        assert {t.codigo for t in titulos} == {
            "ARQUITECTO",
            "MAGISTER EN URBANISMO",
            "DOCTOR EN CIENCIAS",
        }

    async def test_acumula_los_titulos_de_todos_los_periodos(self, uow) -> None:
        """Un docente gana grados con el tiempo: el consolidado los suma."""
        await importar(
            uow,
            [
                cruda(numero=2, pao="2020-1", carrera="A", titulo="MEDICO"),
                cruda(numero=3, pao="2026-1", carrera="B", titulo="MEDICO & MAGISTER EN SALUD"),
            ],
        )
        docente = next(iter(uow.docentes.datos.values()))
        assert len(docente.titulos_ids) == 2

    async def test_un_titulo_repetido_se_crea_una_vez(self, uow) -> None:
        await importar(
            uow,
            [
                cruda(numero=2, identificacion="1710034065", titulo="MEDICO"),
                cruda(numero=3, identificacion="0926687856", titulo="MEDICO"),
            ],
        )
        titulos = await uow.catalogos.listar_todos(TipoCatalogo.TITULO_PROFESIONAL)
        assert len(titulos) == 1


class TestClaveNatural:
    async def test_la_sede_distingue_dos_filas_del_mismo_docente(self, uow) -> None:
        """Un docente si dicta la misma carrera en dos campus el mismo periodo:
        ocurre 118 veces en el consolidado historico."""
        resultado = await importar(
            uow,
            [
                cruda(numero=2, sede="QUITO", horas={"Da": 4.0}),
                cruda(numero=3, sede="CUENCA", horas={"Da": 6.0}),
            ],
        )
        assert resultado.filas_creadas == 2
        assert resultado.filas_consolidadas == 0

    async def test_consolida_las_filas_que_comparten_clave_natural(self, uow) -> None:
        """El origen trae la misma carga dos veces con repartos distintos.

        Se suman en lugar de quedarse con una: el total es el dato que la
        institucion reporta.
        """
        resultado = await importar(
            uow,
            [
                cruda(numero=2, sede="QUITO", horas={"Da": 4.0, "Db": 0.5}),
                cruda(numero=3, sede="QUITO", horas={"Da": 6.0, "Db": 0.5}),
            ],
        )
        assert resultado.filas_creadas == 1
        assert resultado.filas_consolidadas == 1

        fila = next(iter(uow.distributivo.datos.values()))
        assert fila.total_horas == 11.0

    async def test_cada_consolidacion_queda_informada(self, uow) -> None:
        """Consolidar en silencio impediria revisar cual era la carga correcta."""
        resultado = await importar(
            uow,
            [cruda(numero=10, sede="QUITO"), cruda(numero=11, sede="QUITO")],
        )
        assert len(resultado.consolidaciones) == 1
        aviso = resultado.consolidaciones[0]
        assert aviso.filas_origen == (10, 11)
        assert aviso.identificacion == "1710034065"

    async def test_la_sede_ausente_no_abre_una_rendija(self, uow) -> None:
        """Dos filas sin sede comparten clave natural y deben consolidarse."""
        resultado = await importar(uow, [cruda(numero=2, sede=None), cruda(numero=3, sede=None)])
        assert resultado.filas_creadas == 1
        assert resultado.filas_consolidadas == 1


class TestRechazos:
    async def test_una_fila_mala_no_aborta_la_carga(self, uow) -> None:
        resultado = await importar(
            uow,
            [
                cruda(numero=2, identificacion="1710034065"),
                cruda(numero=3, identificacion="06452930/5"),
                cruda(numero=4, identificacion="0926687856"),
            ],
        )
        assert resultado.filas_creadas == 2
        assert len(resultado.rechazadas) == 1
        assert resultado.rechazadas[0].numero_fila == 3
        assert not resultado.exitosa

    @pytest.mark.parametrize(
        ("campo", "valor", "motivo"),
        [
            ("carrera", None, "carrera"),
            ("carrera", "0", "carrera"),
            ("pao", "2026", "PAO"),
            ("facultad", "", "facultad"),
        ],
    )
    async def test_rechaza_filas_sin_datos_obligatorios(
        self, uow, campo: str, valor: str | None, motivo: str
    ) -> None:
        resultado = await importar(uow, [cruda(**{campo: valor})])  # type: ignore[arg-type]
        assert resultado.filas_creadas == 0
        assert motivo.lower() in resultado.rechazadas[0].motivo.lower()

    async def test_informa_el_numero_de_fila_del_archivo(self, uow) -> None:
        """Sin el numero, corregir el origen es buscar a ciegas."""
        resultado = await importar(uow, [cruda(numero=4821, carrera=None)])
        assert resultado.rechazadas[0].numero_fila == 4821

    async def test_una_carga_vacia_se_rechaza(self, uow) -> None:
        from app.domain.errors import ErrorValidacion

        with pytest.raises(ErrorValidacion):
            await importar(uow, [])


class TestGrafiaDelNombre:
    async def test_elige_la_grafia_mas_frecuente(self, uow) -> None:
        """El origen trae varias grafias del mismo docente entre periodos.

        Elegir siempre la misma hace que la persona sea un solo texto en todo el
        historico, que es lo que permite agrupar por docente.
        """
        await importar(
            uow,
            [
                cruda(numero=2, pao="2024-1", carrera="A", nombre="GUTIERREZ MORA DOLORES"),
                cruda(numero=3, pao="2025-1", carrera="B", nombre="GUTIERREZ MORA DOLORES"),
                cruda(numero=4, pao="2026-1", carrera="C", nombre="GUTIÉRREZ MORA DOLORES"),
            ],
        )
        docente = next(iter(uow.docentes.datos.values()))
        assert docente.nombre_completo == "GUTIERREZ MORA DOLORES"

    async def test_a_igual_frecuencia_prefiere_la_mas_completa(self, uow) -> None:
        await importar(
            uow,
            [
                cruda(numero=2, pao="2025-1", carrera="A", nombre="PEREZ JUAN"),
                cruda(numero=3, pao="2026-1", carrera="B", nombre="PEREZ GOMEZ JUAN CARLOS"),
            ],
        )
        docente = next(iter(uow.docentes.datos.values()))
        assert docente.nombre_completo == "PEREZ GOMEZ JUAN CARLOS"


class TestReemplazarExistentes:
    """Recarga de un periodo ya cargado.

    Sin esta opcion la segunda carga chocaba con la clave natural y obligaba a
    vaciar el periodo antes, perdiendo de paso las materias enlazadas.
    """

    async def test_sin_la_opcion_se_duplica_la_clave(self, uow) -> None:
        await importar(uow, [cruda(horas={"Da": 10.0})])
        await importar(uow, [cruda(horas={"Da": 20.0})])
        # El doble en memoria no impone la restriccion; en SQL fallaria. Lo que
        # se comprueba aqui es que sin la opcion se intenta crear otra fila.
        assert len(uow.distributivo.datos) == 2

    async def test_con_la_opcion_actualiza_en_vez_de_crear(self, uow) -> None:
        await importar(uow, [cruda(horas={"Da": 10.0})])
        original = next(iter(uow.distributivo.datos.values()))

        caso = ImportarDistributivo(uow)
        resultado = await caso(
            EntradaImportacion(filas=(cruda(horas={"Da": 20.0}),), reemplazar_existentes=True),
            ContextoEjecucion.sistema(),
        )

        assert resultado.filas_creadas == 0
        assert resultado.filas_actualizadas == 1
        assert len(uow.distributivo.datos) == 1
        fila = next(iter(uow.distributivo.datos.values()))
        assert fila.total_horas == 20.0
        assert fila.id == original.id, "el id se conserva: de el cuelgan las materias"

    async def test_distingue_altas_de_cambios(self, uow) -> None:
        await importar(uow, [cruda(carrera="MEDICINA", horas={"Da": 10.0})])

        caso = ImportarDistributivo(uow)
        resultado = await caso(
            EntradaImportacion(
                filas=(
                    cruda(numero=2, carrera="MEDICINA", horas={"Da": 11.0}),
                    cruda(numero=3, carrera="ODONTOLOGIA", horas={"Da": 12.0}),
                ),
                reemplazar_existentes=True,
            ),
            ContextoEjecucion.sistema(),
        )

        assert resultado.filas_actualizadas == 1
        assert resultado.filas_creadas == 1
        assert len(uow.distributivo.datos) == 2

    async def test_la_sede_forma_parte_de_la_clave(self, uow) -> None:
        await importar(uow, [cruda(sede="QUITO", horas={"Da": 10.0})])

        caso = ImportarDistributivo(uow)
        resultado = await caso(
            EntradaImportacion(
                filas=(cruda(sede="SANTO DOMINGO", horas={"Da": 10.0}),),
                reemplazar_existentes=True,
            ),
            ContextoEjecucion.sistema(),
        )
        # Mismo docente, periodo y carrera, pero otro campus: es otra fila.
        assert resultado.filas_creadas == 1
        assert len(uow.distributivo.datos) == 2


class TestPeriodoInterciclo:
    """El periodo corto entre dos ordinarios."""

    async def test_va_a_un_periodo_propio(self, uow) -> None:
        await importar(uow, [cruda(pao="2026-1", horas={"Da": 10.0})])

        caso = ImportarDistributivo(uow)
        await caso(
            EntradaImportacion(
                filas=(
                    FilaCrudaDistributivo(
                        numero_fila=3,
                        identificacion="1710034065",
                        pao="2026-1",
                        facultad="FCSEE",
                        carrera="MEDICINA",
                        interciclo=True,
                        horas={"Da": 4.0},
                    ),
                ),
            ),
            ContextoEjecucion.sistema(),
        )

        paos = await uow.catalogos.listar_todos(TipoCatalogo.PAO)
        codigos = sorted(p.codigo for p in paos)
        # El ordinario termina en 1 y el interciclo en 0, como los nombra el
        # SICAF. Son dos periodos, no dos formas de escribir uno.
        assert codigos == ["261650", "261651"]
        assert len(uow.distributivo.datos) == 2

    async def test_el_nombre_lo_distingue_en_pantalla(self, uow) -> None:
        caso = ImportarDistributivo(uow)
        await caso(
            EntradaImportacion(
                filas=(
                    FilaCrudaDistributivo(
                        numero_fila=2,
                        identificacion="1710034065",
                        pao="2026-1",
                        facultad="FCSEE",
                        carrera="MEDICINA",
                        interciclo=True,
                        horas={"Da": 4.0},
                    ),
                ),
            ),
            ContextoEjecucion.sistema(),
        )
        paos = await uow.catalogos.listar_todos(TipoCatalogo.PAO)
        assert paos[0].nombre == "2026-1 GRADO INTERCICLO"


class TestCamposDelSistemaAcademico:
    async def test_llegan_a_la_fila(self, uow) -> None:
        from app.domain.enums import EstadoValidacion
        from app.domain.ports.importacion import DatosSistemaAcademico

        caso = ImportarDistributivo(uow)
        await caso(
            EntradaImportacion(
                filas=(
                    FilaCrudaDistributivo(
                        numero_fila=2,
                        identificacion="1710034065",
                        pao="2026-2",
                        facultad="FAU",
                        carrera="ARQUITECTURA",
                        horas={"Da": 10.0},
                        sistema=DatosSistemaAcademico(
                            estado_validacion="OK_EXCEPCION",
                            fase="Planificación",
                            semanas=16,
                            relacion_laboral="Dependencia Laboral",
                            tutor_posgrado=True,
                        ),
                    ),
                ),
            ),
            ContextoEjecucion.sistema(),
        )
        f = next(iter(uow.distributivo.datos.values()))
        assert f.estado_validacion is EstadoValidacion.OK_EXCEPCION
        assert f.semanas == 16
        assert f.tutor_posgrado is True
        assert f.tutor_medicina is False

    async def test_el_consolidado_los_deja_vacios(self, uow) -> None:
        # Vacio significa «el dato no existia», no «sin validar».
        await importar(uow, [cruda(horas={"Da": 8.0})])
        f = next(iter(uow.distributivo.datos.values()))

        assert f.estado_validacion is None
        assert f.semanas is None
        assert f.fase is None
