"""Pruebas del lector del distributivo del sistema academico.

Lo que se protege aqui es la traduccion entre dos formatos: el ERP entrega la
sede, el nivel y la modalidad en columnas aparte, y el consolidado los lleva
dentro del nombre de la carrera. Si esa recomposicion cambia, la misma carrera
entra dos veces al catalogo con dos nombres.
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from app.infrastructure.importadores.pao_excel import LectorPaoExcel

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


class TestFilasAgregadas:
    """El origen junta con comas cuando un docente dicta en varias."""

    def test_rechaza_varias_carreras_en_una_celda(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(**{"Carrera/Programa": "ALIMENTOS, MECATRÓNICA"}))
        filas, rechazadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas == []
        assert len(rechazadas) == 1
        assert "carrera" in rechazadas[0][2]

    def test_rechaza_varias_sedes(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(tmp_path, fila(Sede="SEDE QUITO, SEDE SANTO DOMINGO"))
        filas, rechazadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert filas == []
        assert "sede" in rechazadas[0][2]

    def test_una_mala_no_arrastra_a_las_demas(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        archivo = hacer_archivo(
            tmp_path,
            fila(Identificación="1710034065"),
            fila(Identificación="0912345678", **{"Carrera/Programa": "A, B"}),
        )
        filas, rechazadas = LectorPaoExcel().leer(archivo, pao="2026-2")

        assert len(filas) == 1
        assert len(rechazadas) == 1


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
