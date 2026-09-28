"""Pruebas del lector del distributivo del sistema academico.

Lo que se protege aqui es la traduccion entre dos formatos: el ERP entrega la
sede, el nivel y la modalidad en columnas aparte, y el consolidado los lleva
dentro del nombre de la carrera. Si esa recomposicion cambia, la misma carrera
entra dos veces al catalogo con dos nombres.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.domain.errors import ErrorValidacion
from app.infrastructure.importadores.pao_excel import SIN_CARRERA, LectorPaoExcel

pytestmark = pytest.mark.unit

CABECERA = [
    "No.",
    "Identificación",
    "Apellidos y Nombres",
    "Sede",
    "Nivel",
    "Facultad",
    "Carrera/Programa",
    "Modalidad",
    "Periodo",
    "Da",
    "Db",
    "Ga",
    "Ia",
    "Va",
    "Medida",
    "Titularidad",
    "Categoría",
    "Dedicación",
    "Relación Laboral",
    "Estado de la Validación",
    "Estado de Lote/Proceso",
    "Generación de contrato",
    "Estado de Contrato",
    "N.º Semanas",
    "Fase",
    "Tutores Posgrado",
    "Tutores Medicina",
]


def hacer_archivo(tmp_path, *filas):  # type: ignore[no-untyped-def]
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Distributivo"
    hoja.append(CABECERA)
    for f in filas:
        hoja.append(f)
    ruta = tmp_path / "pao.xlsx"
    libro.save(ruta)
    return ruta


def fila(**cambios):  # type: ignore[no-untyped-def]
    base = {
        "No.": 1,
        "Identificación": "1710034065",
        "Apellidos y Nombres": "PEREZ JUAN",
        "Sede": "SEDE QUITO",
        "Nivel": "GRADO",
        "Facultad": "ARQUITECTURA Y URBANISMO",
        "Carrera/Programa": "ARQUITECTURA",
        "Modalidad": "PRESENCIAL",
        "Periodo": "",
        "Da": 10,
        "Db": 2,
        "Ga": 0,
        "Ia": 0,
        "Va": 0,
        "Medida": "N/A",
        "Titularidad": "NO TITULAR",
        "Categoría": "AUXILIAR",
        "Dedicación": "TIEMPO COMPLETO",
        "Relación Laboral": "Dependencia Laboral",
        "Estado de la Validación": "OK",
        "Estado de Lote/Proceso": "",
        "Generación de contrato": "",
        "Estado de Contrato": "",
        "N.º Semanas": 16,
        "Fase": "Planificación",
        "Tutores Posgrado": "No",
        "Tutores Medicina": "No",
    }
    base.update(cambios)
    return [base[c] for c in CABECERA]


class TestNombreDeLaCarrera:
    """El ERP la entrega en cuatro columnas; el consolidado, en una cadena."""

    def test_recompone_sede_nivel_y_modalidad(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila()), pao="2026-2")

        assert filas[0].carrera == "UIO:ARQUITECTURA - GRADO - PRESENCIAL"

    @pytest.mark.parametrize(
        ("sede", "prefijo"),
        [
            ("SEDE QUITO", "UIO"),
            ("SEDE SANTO DOMINGO", "STO"),
            ("CAMPUS CUENCA", "CUE"),
            ("RICARDO HIDALGO OTTOLENGHI", "MON"),
        ],
    )
    def test_cada_sede_tiene_su_prefijo(self, tmp_path, sede, prefijo) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila(Sede=sede)), pao="2026-2")
        assert filas[0].carrera.startswith(f"{prefijo}:")

    def test_sin_prefijo_conocido_deja_el_nombre_solo(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Es lo que hace el consolidado con carreras como `MEDICINA (R)`.
        filas, _ = LectorPaoExcel().leer(
            hacer_archivo(tmp_path, fila(Sede="OTRO CAMPUS")), pao="2026-2"
        )
        assert filas[0].carrera == "ARQUITECTURA - GRADO - PRESENCIAL"

    def test_omite_los_tramos_sin_dato(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(
            hacer_archivo(tmp_path, fila(Nivel="N/A", Modalidad="N/A")), pao="2026-2"
        )
        assert filas[0].carrera == "UIO:ARQUITECTURA"


class TestFilasCombinadas:
    """El origen junta con comas cuando una sola carga cuenta para varias.

    Ya no se rechazan: se explotan en una fila por combinacion, todas con la
    misma carga de horas, compartiendo `grupo_combinado_id`.
    """

    def test_explota_varias_carreras_en_una_celda(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Carrera/Programa": "ALIMENTOS, MECATRÓNICA"}))
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert [f.carrera for f in filas] == [
            "UIO:ALIMENTOS - GRADO - PRESENCIAL",
            "UIO:MECATRÓNICA - GRADO - PRESENCIAL",
        ]
        assert len(combinadas) == 1
        assert combinadas[0].combinaciones == 2
        assert combinadas[0].ambiguo is False

    def test_explota_varias_sedes_en_una_celda(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(Sede="SEDE QUITO, SEDE SANTO DOMINGO"))
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert [f.sede for f in filas] == ["SEDE QUITO", "SEDE SANTO DOMINGO"]
        assert [f.carrera for f in filas] == [
            "UIO:ARQUITECTURA - GRADO - PRESENCIAL",
            "STO:ARQUITECTURA - GRADO - PRESENCIAL",
        ]
        assert combinadas[0].ambiguo is False

    def test_pareo_ambiguo_genera_todas_las_combinaciones(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Con carrera y sede combinadas a la vez no hay forma de saber el
        pareo real: se generan todas las combinaciones y se marca `ambiguo`."""
        archivo = hacer_archivo(
            tmp_path,
            fila(
                **{"Carrera/Programa": "ALIMENTOS, MECATRÓNICA"},
                Sede="SEDE QUITO, SEDE SANTO DOMINGO",
            ),
        )
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 4
        assert combinadas[0].combinaciones == 4
        assert combinadas[0].ambiguo is True

    def test_las_horas_no_se_reparten(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """La carga cuenta completa en cada combinacion, no dividida."""
        archivo = hacer_archivo(
            tmp_path, fila(**{"Carrera/Programa": "ALIMENTOS, MECATRÓNICA"}, Da=10)
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas[0].horas["Da"] == 10.0
        assert filas[1].horas["Da"] == 10.0

    def test_las_filas_explotadas_comparten_grupo_combinado(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Carrera/Programa": "ALIMENTOS, MECATRÓNICA"}))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas[0].grupo_combinado_id is not None
        assert filas[0].grupo_combinado_id == filas[1].grupo_combinado_id

    def test_una_fila_sin_combinar_no_tiene_grupo(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, combinadas = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila()), pao="2026-2")

        assert filas[0].grupo_combinado_id is None
        assert combinadas == []

    def test_una_fila_con_grupo_no_arrastra_a_las_demas(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path,
            fila(Identificación="1710034065"),
            fila(Identificación="0912345678", **{"Carrera/Programa": "A, B"}),
        )
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 3
        assert len(combinadas) == 1
        assert filas[0].grupo_combinado_id is None


class TestCarreraVacia:
    """Algunas filas no traen ninguna carrera: la asignacion no se hizo aun."""

    def test_sin_carrera_usa_el_marcador(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path,
            fila(**{"Carrera/Programa": "", "Sede": "", "Nivel": "N/A", "Modalidad": "N/A"}),
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 1
        assert filas[0].carrera == SIN_CARRERA
        assert filas[0].grupo_combinado_id is None

    def test_no_se_confunde_con_una_combinacion(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Una sola fila con el marcador, no una explosion."""
        archivo = hacer_archivo(tmp_path, fila(**{"Carrera/Programa": "N/A"}))
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 1
        assert combinadas == []


class TestPeriodoCombinado:
    """Desde 2026-2 `Periodo` puede traer el codigo de mas de un PAO a la vez:
    la misma carga cuenta para grado y posgrado el mismo semestre."""

    def test_un_periodo_no_cambia_el_nivel(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Con un solo codigo no hay nada que decidir: manda la columna Nivel."""
        filas, _ = LectorPaoExcel().leer(
            hacer_archivo(tmp_path, fila(Periodo="262651", Nivel="GRADO")), pao="2026-2"
        )
        assert len(filas) == 1
        assert filas[0].nivel == "GRADO"

    def test_dos_periodos_explotan_por_nivel(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(Periodo="262751, 262651"))
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert sorted(f.nivel for f in filas) == ["GRADO", "POSGRADO"]
        assert combinadas[0].combinaciones == 2
        # Solo el periodo se combino: no hay ambiguedad de carrera/sede.
        assert combinadas[0].ambiguo is False

    def test_las_dos_copias_llevan_la_misma_carga(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(Periodo="262751, 262651", Da=10))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert {f.horas["Da"] for f in filas} == {10.0}
        assert filas[0].grupo_combinado_id == filas[1].grupo_combinado_id

    def test_un_codigo_invalido_no_tumba_la_fila(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Un codigo que no se reconoce se ignora; la fila no se pierde."""
        archivo = hacer_archivo(tmp_path, fila(Periodo="262651, no-es-un-codigo"))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 1
        assert filas[0].nivel == "GRADO"

    def test_periodo_y_carrera_combinados_a_la_vez(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path,
            fila(Periodo="262751, 262651", **{"Carrera/Programa": "ARQUITECTURA, DISEÑO"}),
        )
        filas, combinadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        # 2 periodos x 2 carreras x 1 sede.
        assert len(filas) == 4
        assert combinadas[0].combinaciones == 4
        # La ambiguedad es de carrera/sede, no de periodo.
        assert combinadas[0].ambiguo is False


class TestDatosDelSistemaAcademico:
    def test_traduce_el_estado_de_validacion(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path,
            fila(**{"Estado de la Validación": "OK"}),
            fila(Identificación="0912345678", **{"Estado de la Validación": "Ok, excepción"}),
            fila(
                Identificación="0912345679", **{"Estado de la Validación": "Validación Pendiente"}
            ),
            fila(Identificación="0912345670", **{"Estado de la Validación": "Error"}),
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert [f.sistema.estado_validacion for f in filas] == [
            "OK",
            "OK_EXCEPCION",
            "PENDIENTE",
            "ERROR",
        ]

    def test_lee_semanas_fase_y_relacion(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila()), pao="2026-2")
        sistema = filas[0].sistema

        assert sistema.semanas == 16
        assert sistema.fase == "Planificación"
        assert sistema.relacion_laboral == "Dependencia Laboral"

    def test_las_marcas_de_tutoria(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path, fila(**{"Tutores Posgrado": "Sí", "Tutores Medicina": "No"})
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas[0].sistema.tutor_posgrado is True
        assert filas[0].sistema.tutor_medicina is False


class TestEstadoDeLoteYDeContrato:
    """Avance de la contratacion administrativa, distinto de la validacion
    academica que ya cubre `estado_validacion`."""

    def test_lee_el_estado_de_lote(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Estado de Lote/Proceso": "En revisión por DGA"}))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")
        assert filas[0].sistema.estado_lote == "En revisión por DGA"

    def test_lee_el_estado_de_contrato(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Estado de Contrato": "Firmado Docente"}))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")
        assert filas[0].sistema.estado_contrato == "Firmado Docente"

    def test_lee_la_generacion_de_contrato(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Generación de contrato": "Si"}))
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")
        assert filas[0].sistema.generacion_contrato == "Si"

    def test_sin_dato_queda_vacio(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila()), pao="2026-2")
        assert filas[0].sistema.estado_lote is None
        assert filas[0].sistema.estado_contrato is None
        assert filas[0].sistema.generacion_contrato is None


class TestFacultadYPeriodo:
    def test_traduce_el_nombre_de_la_facultad_a_su_codigo(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(hacer_archivo(tmp_path, fila()), pao="2026-2")
        # Sin esto la facultad entraria dos veces: con su nombre y con su sigla.
        assert filas[0].facultad == "FAU"

    def test_la_marca_de_interciclo_viaja_en_la_fila(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila())
        normales, _ = LectorPaoExcel().leer(archivo, pao="2026-1")
        cortas, _ = LectorPaoExcel().leer(archivo, pao="2026-1", interciclo=True)

        assert normales[0].interciclo is False
        assert cortas[0].interciclo is True


class TestCategoria:
    """El ERP antepone «TITULAR» a las categorias del escalafon."""

    @pytest.mark.parametrize(
        ("origen", "esperada"),
        [
            ("TITULAR AUXILIAR", "AUXILIAR"),
            ("TITULAR AGREGADO", "AGREGADO"),
            ("TITULAR PRINCIPAL", "PRINCIPAL"),
            ("TITULAR AUXILIAR 1", "AUXILIAR"),
            # Las que ya coinciden pasan intactas.
            ("OCASIONAL", "OCASIONAL"),
            ("INVITADO", "INVITADO"),
            ("TÉCNICO DOCENTE", "TÉCNICO DOCENTE"),
        ],
    )
    def test_se_traduce_a_la_del_consolidado(self, tmp_path, origen, esperada) -> None:  # type: ignore[no-untyped-def]
        # Sin esto cada categoria entraria dos veces y un conteo saldria partido.
        filas, _ = LectorPaoExcel().leer(
            hacer_archivo(tmp_path, fila(**{"Categoría": origen})), pao="2026-2"
        )
        assert filas[0].categoria == esperada

    def test_sin_dato_queda_vacia(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        filas, _ = LectorPaoExcel().leer(
            hacer_archivo(tmp_path, fila(**{"Categoría": "N/A"})), pao="2026-2"
        )
        assert filas[0].categoria is None


class TestOrigenDelArchivo:
    """De donde se lee: ruta o contenido, `.xlsx` o el `.xls` de 2003.

    El sistema academico exporta en formato Excel 97-2003, que openpyxl no
    abre. Antes habia que convertirlo a mano antes de cada carga; leerlo
    directamente es lo que permite subirlo desde la interfaz.
    """

    def test_lee_desde_bytes_igual_que_desde_la_ruta(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila())

        desde_ruta, _ = LectorPaoExcel().leer(archivo, pao="2026-2")
        desde_bytes, _ = LectorPaoExcel().leer(archivo.read_bytes(), pao="2026-2")

        assert desde_bytes == desde_ruta

    def test_lee_el_formato_de_excel_97_2003(self) -> None:
        xlwt = pytest.importorskip("xlwt", reason="solo para fabricar un .xls de prueba")

        libro = xlwt.Workbook()
        hoja = libro.add_sheet("Distributivo")
        for columna, titulo in enumerate(CABECERA):
            hoja.write(0, columna, titulo)
        for columna, valor in enumerate(fila()):
            hoja.write(1, columna, valor)

        memoria = BytesIO()
        libro.save(memoria)
        contenido = memoria.getvalue()

        # Es realmente un documento OLE2, que es lo que distingue al formato.
        assert contenido[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

        filas, _ = LectorPaoExcel().leer(contenido, pao="2026-2")

        assert len(filas) == 1
        assert filas[0].identificacion == "1710034065"
        assert filas[0].carrera == "UIO:ARQUITECTURA - GRADO - PRESENCIAL"
        assert filas[0].sistema.semanas == 16

    def test_un_archivo_que_no_es_una_hoja_de_calculo_se_rechaza(self) -> None:
        with pytest.raises(ErrorValidacion):
            LectorPaoExcel().leer(b"esto no es un libro de Excel", pao="2026-2")

    def test_un_archivo_vacio_se_rechaza(self) -> None:
        with pytest.raises(ErrorValidacion):
            LectorPaoExcel().leer(b"", pao="2026-2")

    def test_una_ruta_que_no_existe_se_rechaza(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ErrorValidacion):
            LectorPaoExcel().leer(tmp_path / "no-esta.xlsx", pao="2026-2")


#: Cabecera del reporte completo del PAO: dos filas, con `Titularidad`,
#: `Categoria`, `Dedicacion` y `Relacion Laboral` repetidas bajo `Antigua`
#: (columnas 9-12) y bajo `Nueva` (columnas 18-21).
_CABECERA_REPORTE_COMPLETO_PRIMARIA = [
    "No.",
    "Identificación",
    "Apellidos y Nombres",
    "Sede",
    "Nivel",
    "Facultad",
    "Carrera/Programa",
    "Modalidad",
    "Antigua",
    "",
    "",
    "",
    "Da",
    "Medida",
    "Nueva",
    "",
    "",
    "",
    "Estado de la Validación",
    "N.º Semanas",
    "Fase",
]
_CABECERA_REPORTE_COMPLETO_SECUNDARIA = [
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "Titularidad",
    "Categoría",
    "Dedicación",
    "Relación Laboral",
    "",
    "",
    "Titularidad",
    "Categoría",
    "Dedicación",
    "Relación Laboral",
    "",
    "",
    "",
]


def hacer_archivo_reporte_completo(tmp_path, *filas):  # type: ignore[no-untyped-def]
    """El PAO tal como lo exporta el sistema completo: varias pestanas, y en
    `Distributivo` dos filas de titulo antes de una cabecera partida en dos."""
    libro = Workbook()
    antecedentes = libro.active
    antecedentes.title = "Antecedentes"
    antecedentes.append(["Esto no es el distributivo"])

    hoja = libro.create_sheet("Distributivo")
    hoja.append([""] * len(_CABECERA_REPORTE_COMPLETO_PRIMARIA))
    hoja.append(["", "DISTRIBUCIÓN HORARIA POR FUNCIONES SUSTANTIVAS Y GESTIÓN"])
    hoja.append(_CABECERA_REPORTE_COMPLETO_PRIMARIA)
    hoja.append(_CABECERA_REPORTE_COMPLETO_SECUNDARIA)
    for f in filas:
        hoja.append(f)

    ruta = tmp_path / "pao_completo.xlsx"
    libro.save(ruta)
    return ruta


def fila_reporte_completo(  # type: ignore[no-untyped-def]
    *, titularidad_antigua="TITULAR", titularidad_nueva="TITULAR", relacion_nueva="N/A"
):
    return [
        1,
        "1710034065",
        "PEREZ JUAN",
        "SEDE QUITO",
        "GRADO",
        "ARQUITECTURA Y URBANISMO",
        "ARQUITECTURA",
        "PRESENCIAL",
        titularidad_antigua,
        "AUXILIAR",
        "TIEMPO COMPLETO",
        "N/A",
        10,
        "N/A",
        titularidad_nueva,
        "AUXILIAR",
        "TIEMPO COMPLETO",
        relacion_nueva,
        "OK",
        16,
        "Planificación",
    ]


class TestReporteCompletoDelPao:
    """El sistema tambien exporta el PAO entero, con `Distributivo` como una
    pestana mas y su cabecera partida en `Antigua` / `Nueva`."""

    def test_ubica_la_hoja_distributivo_aunque_no_sea_la_primera(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo_reporte_completo(tmp_path, fila_reporte_completo())
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 1
        assert filas[0].identificacion == "1710034065"

    def test_usa_el_grupo_nueva_y_descarta_antigua(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo_reporte_completo(
            tmp_path,
            fila_reporte_completo(titularidad_antigua="NO TITULAR", titularidad_nueva="TITULAR"),
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas[0].titularidad == "TITULAR"

    def test_nueva_completa_lo_que_antigua_deja_en_blanco(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Es el caso real: `Antigua` trae `N/A` en Relacion Laboral donde
        # `Nueva` ya tiene el dato corregido.
        archivo = hacer_archivo_reporte_completo(
            tmp_path, fila_reporte_completo(relacion_nueva="Servicios Profesionales")
        )
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas[0].sistema.relacion_laboral == "Servicios Profesionales"

    def test_lee_las_horas_y_los_demas_campos_igual_que_la_hoja_suelta(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo_reporte_completo(tmp_path, fila_reporte_completo())
        filas, _ = LectorPaoExcel().leer(archivo, pao="2026-2")

        f = filas[0]
        assert f.carrera == "UIO:ARQUITECTURA - GRADO - PRESENCIAL"
        assert f.horas == {"Da": 10.0}
        assert f.sistema.semanas == 16
        assert f.sistema.fase == "Planificación"
