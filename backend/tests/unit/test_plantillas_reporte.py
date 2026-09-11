"""Pruebas de las plantillas de exportacion del distributivo.

Lo que importa verificar aqui es que la plantilla del consolidado reproduzca el
archivo de origen columna por columna: es lo unico que hace posible comparar
ambos archivos sin alinearlos a mano.
"""

from __future__ import annotations

import pytest

from app.application.plantillas import (
    COLUMNAS_CONSOLIDADO,
    COLUMNAS_DOCENCIA,
    REGISTRO_PLANTILLAS,
    PlantillaConsolidadoOrigen,
    PlantillaDocenciaPorCarrera,
    RegistroPlantillas,
)
from app.domain.entities.distributivo import Docente, FilaDistributivo
from app.domain.errors import ErrorValidacion
from app.domain.ports.distributivo import (
    FilaDistributivoResuelta,
    FilaReporteDocencia,
    FiltroDistributivo,
)
from app.domain.value_objects_distributivo import DistribucionHoras

#: Cabecera literal del `distributivo.xlsx` de origen, en su orden.
CABECERA_ORIGEN = [
    "IDENTIFICACION", "PAO", "FACULTAD", "CARRERA", "SEDE", "APELLIDOS.Y.NOMBRES",
    "TITULARIDAD", "DEDICACION", "CATEGORIA",
    "Da", "Db", "Dc", "Dd", "De", "Df", "Dg", "Dh", "Di", "Dj", "Dk", "Dl", "Dm", "Dn", "D",
    "Ga", "Gb", "Gc", "Gd", "Ge", "Gf", "Gg", "Gh", "Gi", "Gj", "Gk", "Gl", "Gm", "Gn", "G",
    "Ic", "Ie", "Ig", "Ih", "Ii", "I", "V", "Ia", "Ib", "Id", "If", "Ij",
    "Va", "Vb", "Vc", "Vd", "Ve", "Vf", "Vg", "Vh", "Vi",
    "NIVEL", "CARRERA/PROGRAMA", "TotalHoras", "MEDIDA",
    "NA", "an", "gen", "N.x", "TITULO", "TIPOTITULO", "GENERO", "N.y",
]  # fmt: skip


class _Uow:
    """Unidad de trabajo minima: solo el repositorio que usan las plantillas."""

    def __init__(self, *, reporte=None, resueltas=None) -> None:  # type: ignore[no-untyped-def]
        self.distributivo = _Repo(reporte or [], resueltas or [])


class _Repo:
    def __init__(self, reporte, resueltas) -> None:  # type: ignore[no-untyped-def]
        self._reporte = reporte
        self._resueltas = resueltas

    async def filas_para_reporte(self, filtro):  # type: ignore[no-untyped-def]
        return list(self._reporte)

    async def filas_resueltas(self, filtro):  # type: ignore[no-untyped-def]
        return list(self._resueltas)


def _resuelta(**cambios) -> FilaDistributivoResuelta:  # type: ignore[no-untyped-def]
    docente = Docente(identificacion="1710034065", nombre_completo="PEREZ LUIS")
    base = {
        "fila": FilaDistributivo(
            docente_id=docente.id,
            pao_id=docente.id,
            facultad_id=docente.id,
            carrera_id=docente.id,
            horas=DistribucionHoras.desde_plano({"Da": 10.0, "Ga": 4.0, "Ib": 2.5, "Vc": 1.0}),
            medida="NO APLICA",
        ),
        "docente_identificacion": "1710034065",
        "docente_nombre": "PEREZ LUIS",
        "pao": "2026-1",
        "facultad": "FCID",
        "carrera": "SOFTWARE",
        "programa": "SOFTWARE",
        "sede": "MATRIZ QUITO",
        "nivel": "GRADO",
        "titularidad": "TITULAR",
        "dedicacion": "TIEMPO COMPLETO",
        "categoria": "AUXILIAR 1",
        "tipo_titulo": "MAESTRIA O EQUIVALENTE",
        "genero": "MASCULINO",
        "titulos": ("INGENIERO DE SISTEMAS", "MAGISTER EN SOFTWARE"),
    }
    return FilaDistributivoResuelta(**{**base, **cambios})


# ===========================================================================
# Registro
# ===========================================================================


def test_registro_ofrece_las_dos_plantillas() -> None:
    codigos = [p.codigo for p in REGISTRO_PLANTILLAS.disponibles()]
    assert codigos == ["docencia-carrera", "consolidado-origen"]


def test_sin_codigo_usa_la_institucional() -> None:
    assert REGISTRO_PLANTILLAS.obtener(None).codigo == "docencia-carrera"
    assert REGISTRO_PLANTILLAS.obtener("").codigo == "docencia-carrera"


def test_codigo_desconocido_dice_cuales_hay() -> None:
    with pytest.raises(ErrorValidacion) as error:
        REGISTRO_PLANTILLAS.obtener("inventada")
    assert "consolidado-origen" in str(error.value)


def test_el_registro_admite_plantillas_propias() -> None:
    """Sumar un formato es registrar una clase, no tocar el caso de uso."""
    registro = RegistroPlantillas((PlantillaConsolidadoOrigen(),))
    assert registro.obtener(None).codigo == "consolidado-origen"


# ===========================================================================
# Plantilla del consolidado
# ===========================================================================


def test_las_columnas_son_las_del_archivo_de_origen() -> None:
    assert [c.clave for c in COLUMNAS_CONSOLIDADO] == CABECERA_ORIGEN
    assert [c.titulo for c in COLUMNAS_CONSOLIDADO] == CABECERA_ORIGEN
    assert len(COLUMNAS_CONSOLIDADO) == 72


async def test_la_fila_trae_un_valor_por_cada_columna() -> None:
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert list(fila) == CABECERA_ORIGEN


async def test_los_subtotales_se_recalculan_desde_el_detalle() -> None:
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["D"] == 10.0
    assert fila["G"] == 4.0
    assert fila["I"] == 2.5
    assert fila["V"] == 1.0
    assert fila["TotalHoras"] == 17.5


async def test_las_horas_sin_valor_viajan_vacias_y_no_como_cero() -> None:
    """El origen distingue "no aplica" de "cero horas"; el export tambien."""
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Da"] == 10.0
    assert fila["Db"] is None


async def test_los_titulos_se_rearman_en_una_celda() -> None:
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["TITULO"] == "INGENIERO DE SISTEMAS & MAGISTER EN SOFTWARE"
    assert fila["N.y"] == 2


async def test_las_columnas_residuales_se_reconstruyen() -> None:
    """`an`, `gen` y `N.x` son residuos del cruce; se emiten para que calcen."""
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["an"] == fila["APELLIDOS.Y.NOMBRES"]
    assert fila["gen"] == fila["GENERO"] == "MASCULINO"
    assert fila["N.x"] == 1
    assert fila["NA"] is None


async def test_un_docente_sin_titulos_no_rompe_la_celda() -> None:
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[_resuelta(titulos=())]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["TITULO"] is None
    assert fila["N.y"] == 0


async def test_el_limite_recorta_las_filas_pero_no_los_totales() -> None:
    filas = [_resuelta() for _ in range(5)]
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=filas),  # type: ignore[arg-type]
        FiltroDistributivo(),
        limite=2,
    )
    assert len(contenido.filas) == 2
    assert contenido.total_filas == 5


async def test_cuenta_las_filas_que_dictan_clase_sin_asignatura() -> None:
    con_docencia = _resuelta()
    sin_docencia = _resuelta(
        fila=FilaDistributivo(
            docente_id=con_docencia.fila.docente_id,
            pao_id=con_docencia.fila.pao_id,
            facultad_id=con_docencia.fila.facultad_id,
            carrera_id=con_docencia.fila.carrera_id,
            horas=DistribucionHoras.desde_plano({"Ga": 8.0}),
        )
    )
    contenido = await PlantillaConsolidadoOrigen().construir(
        _Uow(resueltas=[con_docencia, sin_docencia]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    # Solo la que tiene horas de docencia: a quien no dicta no le falta nada.
    assert contenido.sin_asignatura == 1


# ===========================================================================
# Plantilla institucional
# ===========================================================================


def _reporte(**cambios) -> FilaReporteDocencia:  # type: ignore[no-untyped-def]
    base = {
        "numero": 1,
        "nombre": "PEREZ LUIS",
        "titulo_profesional": "INGENIERO DE SISTEMAS",
        "grado_academico": "MAESTRIA O EQUIVALENTE",
        "asignatura": "",
        "anio_inicio_carrera": 2020,
        "jerarquia_docente": "AUXILIAR 1",
        "dedicacion_horaria": "TIEMPO COMPLETO",
        "tipo_contrato": "TITULAR",
        "unidad": "FCID",
        "comuna": "MATRIZ QUITO",
        "anio_actual": 2026,
        "identificacion": "1710034065",
        "carrera": "SOFTWARE",
        "total_horas": 40.0,
        "total_docencia": 32.0,
    }
    return FilaReporteDocencia(**{**base, **cambios})


def test_la_plantilla_institucional_tiene_doce_columnas() -> None:
    assert len(COLUMNAS_DOCENCIA) == 12
    assert COLUMNAS_DOCENCIA[4].clave == "asignatura"


def test_las_cinco_primeras_columnas_van_en_amarillo() -> None:
    assert [c.color_cabecera for c in COLUMNAS_DOCENCIA[:5]] == ["FFFF00"] * 5
    assert {c.color_cabecera for c in COLUMNAS_DOCENCIA[5:]} == {"D9D9D9"}


async def test_la_auditoria_agrega_columnas_al_final() -> None:
    uow = _Uow(reporte=[_reporte()])
    plantilla = PlantillaDocenciaPorCarrera()

    sin = await plantilla.construir(uow, FiltroDistributivo())  # type: ignore[arg-type]
    con = await plantilla.construir(
        uow,  # type: ignore[arg-type]
        FiltroDistributivo(),
        incluir_auditoria=True,
    )
    assert len(sin.columnas) == 12
    assert [c.clave for c in con.columnas[12:]] == ["identificacion", "carrera", "total_horas"]


async def test_informa_cuantas_filas_van_sin_asignatura() -> None:
    contenido = await PlantillaDocenciaPorCarrera().construir(
        _Uow(reporte=[_reporte(), _reporte(asignatura="CALCULO")]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.sin_asignatura == 1
    assert contenido.totales["Sin asignatura registrada"] == 1


async def test_no_cuenta_a_quien_no_dicta_clase() -> None:
    """Sin horas de docencia no falta ninguna asignatura."""
    contenido = await PlantillaDocenciaPorCarrera().construir(
        _Uow(reporte=[_reporte(total_docencia=0.0)]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.sin_asignatura == 0


async def test_sin_pendientes_no_aparece_el_total_de_faltantes() -> None:
    contenido = await PlantillaDocenciaPorCarrera().construir(
        _Uow(reporte=[_reporte(asignatura="CALCULO")]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert "Sin asignatura registrada" not in contenido.totales


async def test_cuenta_docentes_distintos_y_no_filas() -> None:
    """Un docente en dos carreras es dos filas y un solo profesor."""
    contenido = await PlantillaDocenciaPorCarrera().construir(
        _Uow(reporte=[_reporte(), _reporte(numero=2, carrera="TELEMATICA")]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.total_filas == 2
    assert contenido.total_docentes == 1


# ===========================================================================
# Ancho del PDF
# ===========================================================================


def test_el_pdf_rechaza_una_tabla_que_no_cabe_en_la_pagina() -> None:
    """Setenta y dos columnas no son un documento imprimible.

    Antes de esta comprobacion, `reportlab` abortaba a mitad del armado con un
    ancho de celda negativo y la peticion devolvia un 500.
    """
    from app.domain.errors import ReporteDemasiadoAncho
    from app.domain.ports.reportes import TablaReporte
    from app.infrastructure.reportes.pdf import ExportadorPDF

    tabla = TablaReporte(
        titulo="Consolidado",
        columnas=list(COLUMNAS_CONSOLIDADO),
        filas=[dict.fromkeys((c.clave for c in COLUMNAS_CONSOLIDADO), "x")],
    )

    with pytest.raises(ReporteDemasiadoAncho) as error:
        ExportadorPDF().exportar(tabla)

    # El mensaje dice cuantas caben y que hacer en su lugar.
    assert "72 columnas" in str(error.value)
    assert "Excel o CSV" in str(error.value)


def test_el_pdf_acepta_la_plantilla_institucional() -> None:
    from app.domain.ports.reportes import TablaReporte
    from app.infrastructure.reportes.pdf import ExportadorPDF

    tabla = TablaReporte(
        titulo="Cuerpo docente",
        columnas=list(COLUMNAS_DOCENCIA),
        filas=[dict.fromkeys((c.clave for c in COLUMNAS_DOCENCIA), "x")],
    )
    archivo = ExportadorPDF().exportar(tabla)
    assert archivo.contenido.startswith(b"%PDF")
