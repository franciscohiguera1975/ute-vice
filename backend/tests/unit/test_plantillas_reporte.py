"""Pruebas de las plantillas de exportacion del distributivo.

Lo que importa verificar aqui es que la plantilla del consolidado reproduzca el
archivo de origen columna por columna: es lo unico que hace posible comparar
ambos archivos sin alinearlos a mano.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.plantillas import (
    COLUMNAS_CONSOLIDADO,
    COLUMNAS_DOCENCIA,
    COLUMNAS_PAO,
    REGISTRO_PLANTILLAS,
    PlantillaConsolidadoOrigen,
    PlantillaDocenciaPorCarrera,
    PlantillaPaoOrigen,
    RegistroPlantillas,
)
from app.domain.entities.distributivo import Docente, FilaDistributivo
from app.domain.enums import EstadoValidacion
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


class _RelojFijo:
    """Reloj congelado: el caso de uso lo exige para sellar el archivo."""

    def ahora(self):  # type: ignore[no-untyped-def]
        from datetime import UTC, datetime

        return datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


@pytest.fixture
def contexto_admin(roles):  # type: ignore[no-untyped-def]
    from tests.conftest import hacer_usuario

    from app.application.base import ContextoEjecucion
    from app.domain.enums import RolCodigo

    return ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )


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
        "pao": "2026-1 GRADO",
        "pao_semestre": "2026-1",
        "facultad": "FCID",
        "carrera": "SOFTWARE",
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


def test_registro_ofrece_las_tres_plantillas() -> None:
    codigos = [p.codigo for p in REGISTRO_PLANTILLAS.disponibles()]
    assert codigos == ["docencia-carrera", "consolidado-origen", "pao-origen"]


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
# Plantilla del sistema academico (PAO)
# ===========================================================================

#: Cabecera literal de la hoja `Distributivo` que reproduce el sistema, en su
#: orden: D, I, V y G —no el D-G-I-V del consolidado—.
CABECERA_PAO = [
    "No.", "Identificación", "Apellidos y Nombres", "Sede", "Nivel", "Facultad",
    "Carrera/Programa", "Modalidad",
    "Da", "Db", "Dc", "Dd", "De", "Df", "Dg", "Dh", "Di", "Dj", "Dk", "Dl", "Dm", "Dn", "D",
    "Ia", "Ib", "Ic", "Id", "Ie", "If", "Ig", "Ih", "Ii", "Ij", "I",
    "Va", "Vb", "Vc", "Vd", "Ve", "Vf", "Vg", "Vh", "Vi", "V",
    "Ga", "Gb", "Gc", "Gd", "Ge", "Gf", "Gg", "Gh", "Gi", "Gj", "Gk", "Gl", "Gm", "Gn", "G",
    "Total Horas Semanales", "Total Horas Semestrales",
    "Tutores Posgrado", "Tutores Medicina", "Medida",
    "Titularidad", "Categoría", "Dedicación", "Relación Laboral",
    "Estado de la Validación", "Estado de Lote/Proceso", "Generación de contrato",
    "Estado de Contrato", "N.º Semanas", "Fase",
]  # fmt: skip


def _resuelta_pao(**cambios) -> FilaDistributivoResuelta:  # type: ignore[no-untyped-def]
    docente = Docente(identificacion="1717154767", nombre_completo="ALMEIDA NAVARRETE FRANCISCO")
    base = {
        "fila": FilaDistributivo(
            docente_id=docente.id,
            pao_id=docente.id,
            facultad_id=docente.id,
            carrera_id=docente.id,
            horas=DistribucionHoras.desde_plano({"Da": 10.0, "Ga": 4.0, "Ib": 2.5, "Vc": 1.0}),
            medida=None,
            estado_validacion=EstadoValidacion.PENDIENTE,
            fase="Planificación",
            semanas=16,
            relacion_laboral="Dependencia Laboral",
            tutor_posgrado=False,
            tutor_medicina=False,
        ),
        "docente_identificacion": "1717154767",
        "docente_nombre": "ALMEIDA NAVARRETE FRANCISCO",
        "pao": "2026-2 GRADO",
        "pao_semestre": "2026-2",
        "facultad": "FAU",
        "carrera": "UIO:ARQUITECTURA - GRADO - PRESENCIAL",
        "sede": "QUITO",
        "nivel": "GRADO",
        "titularidad": "NO TITULAR",
        "dedicacion": "TIEMPO COMPLETO",
        "categoria": "AUXILIAR",
        "codigo_carrera": "UIO:ARQUITECTURA - GRADO - PRESENCIAL",
        "codigo_sede": "QUITO",
        "codigo_nivel": "GRADO",
        "codigo_titularidad": "NO TITULAR",
        "codigo_dedicacion": "TIEMPO COMPLETO",
        "codigo_categoria": "AUXILIAR",
    }
    return FilaDistributivoResuelta(**{**base, **cambios})


def test_las_columnas_son_las_de_la_hoja_distributivo() -> None:
    assert [c.clave for c in COLUMNAS_PAO] == CABECERA_PAO
    assert [c.titulo for c in COLUMNAS_PAO] == CABECERA_PAO


async def test_pao_la_fila_trae_un_valor_por_cada_columna() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert list(contenido.filas[0]) == CABECERA_PAO


async def test_pao_numera_las_filas_de_salida_desde_uno() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao(), _resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert [f["No."] for f in contenido.filas] == [1, 2]


async def test_pao_separa_carrera_y_modalidad_por_el_nivel_conocido() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Carrera/Programa"] == "ARQUITECTURA"
    assert fila["Nivel"] == "GRADO"
    assert fila["Modalidad"] == "PRESENCIAL"


async def test_pao_separa_la_modalidad_sin_nivel() -> None:
    """Sin nivel, `_carrera()` solo pudo haber agregado la modalidad."""
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(
            resueltas=[
                _resuelta_pao(
                    codigo_carrera="UIO:MEDICINA - PRESENCIAL",
                    codigo_nivel=None,
                    nivel=None,
                )
            ]
        ),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Carrera/Programa"] == "MEDICINA"
    assert fila["Modalidad"] == "PRESENCIAL"


async def test_pao_sin_prefijo_de_sede_deja_el_nombre_de_carrera_solo() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(
            resueltas=[_resuelta_pao(codigo_carrera="MEDICINA (R)", codigo_nivel=None, nivel=None)]
        ),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Carrera/Programa"] == "MEDICINA (R)"
    assert fila["Modalidad"] is None


async def test_pao_la_facultad_vuelve_a_su_nombre_largo() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Facultad"] == "ARQUITECTURA Y URBANISMO"


async def test_pao_una_facultad_sin_sigla_conocida_pasa_intacta() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao(facultad="FCID")]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Facultad"] == "FCID"


async def test_pao_la_categoria_vuelve_a_anteponer_titular() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Categoría"] == "TITULAR AUXILIAR"


async def test_pao_una_categoria_sin_escalafon_pasa_intacta() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao(codigo_categoria="OCASIONAL", categoria="OCASIONAL")]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Categoría"] == "OCASIONAL"


async def test_pao_el_estado_de_validacion_vuelve_al_texto_del_origen() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Estado de la Validación"] == "VALIDACIÓN PENDIENTE"


async def test_pao_el_estado_de_lote_y_de_contrato_salen_tal_como_se_guardaron() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(
            resueltas=[
                _resuelta_pao(
                    fila=FilaDistributivo(
                        docente_id=uuid4(),
                        pao_id=uuid4(),
                        facultad_id=uuid4(),
                        carrera_id=uuid4(),
                        horas=DistribucionHoras.vacia(),
                        estado_lote="En revisión por DGA",
                        estado_contrato="Firmado Docente",
                        generacion_contrato="Si",
                    )
                )
            ]
        ),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Estado de Lote/Proceso"] == "EN REVISIÓN POR DGA"
    assert fila["Estado de Contrato"] == "FIRMADO DOCENTE"
    assert fila["Generación de contrato"] == "SI"


async def test_pao_las_marcas_de_tutoria_salen_como_si_o_no() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(
            resueltas=[
                _resuelta_pao(
                    fila=FilaDistributivo(
                        docente_id=uuid4(),
                        pao_id=uuid4(),
                        facultad_id=uuid4(),
                        carrera_id=uuid4(),
                        horas=DistribucionHoras.vacia(),
                        semanas=16,
                        tutor_posgrado=True,
                        tutor_medicina=False,
                    )
                )
            ]
        ),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Tutores Posgrado"] == "Sí"
    assert fila["Tutores Medicina"] == "No"


async def test_pao_las_horas_semestrales_multiplican_por_las_semanas() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(resueltas=[_resuelta_pao()]),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    fila = contenido.filas[0]
    assert fila["Total Horas Semanales"] == 17.5
    assert fila["Total Horas Semestrales"] == 280.0


async def test_pao_sin_semanas_las_horas_semestrales_quedan_vacias() -> None:
    contenido = await PlantillaPaoOrigen().construir(
        _Uow(
            resueltas=[
                _resuelta_pao(
                    fila=FilaDistributivo(
                        docente_id=uuid4(),
                        pao_id=uuid4(),
                        facultad_id=uuid4(),
                        carrera_id=uuid4(),
                        horas=DistribucionHoras.desde_plano({"Da": 10.0}),
                        semanas=None,
                    )
                )
            ]
        ),  # type: ignore[arg-type]
        FiltroDistributivo(),
    )
    assert contenido.filas[0]["Total Horas Semestrales"] is None


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


# ===========================================================================
# Seleccion multiple
# ===========================================================================


class _UowConCatalogos:
    """Unidad de trabajo con catalogos, para el caso de uso del reporte."""

    def __init__(self, elementos, reporte=None):  # type: ignore[no-untyped-def]
        self.catalogos = _RepoCatalogos(elementos)
        self.distributivo = _RepoConFiltro(reporte or [])
        self.commits = 0

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *_):  # type: ignore[no-untyped-def]
        return False


class _RepoCatalogos:
    def __init__(self, elementos):  # type: ignore[no-untyped-def]
        self._por_id = {e.id: e for e in elementos}

    async def obtener(self, tipo, elemento_id):  # type: ignore[no-untyped-def]
        elemento = self._por_id.get(elemento_id)
        return elemento if elemento is not None and elemento.tipo is tipo else None


class _RepoConFiltro:
    """Guarda el filtro recibido: es lo que las pruebas quieren comprobar."""

    def __init__(self, reporte):  # type: ignore[no-untyped-def]
        self._reporte = reporte
        self.ultimo_filtro = None

    async def filas_para_reporte(self, filtro):  # type: ignore[no-untyped-def]
        self.ultimo_filtro = filtro
        return list(self._reporte)

    async def filas_resueltas(self, filtro):  # type: ignore[no-untyped-def]
        self.ultimo_filtro = filtro
        return []


def _catalogo(tipo, codigo, nombre=None):  # type: ignore[no-untyped-def]
    from app.domain.entities.catalogo import ElementoCatalogo

    return ElementoCatalogo(tipo=tipo, codigo=codigo, nombre=nombre or codigo)


async def test_el_reporte_admite_varios_periodos_y_facultades(contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Un reporte rara vez es de un periodo y una carrera."""
    from app.application.casos_uso.reporte_distributivo import (
        EntradaReporteDistributivo,
        VistaPreviaReporteDistributivo,
    )
    from app.domain.entities.catalogo import TipoCatalogo

    p1, p2 = _catalogo(TipoCatalogo.PAO, "252651"), _catalogo(TipoCatalogo.PAO, "261651")
    f1, f2 = _catalogo(TipoCatalogo.FACULTAD, "FCID"), _catalogo(TipoCatalogo.FACULTAD, "FCSEE")
    uow = _UowConCatalogos([p1, p2, f1, f2], reporte=[_reporte()])

    vista = await VistaPreviaReporteDistributivo(uow, _RelojFijo())(  # type: ignore[arg-type]
        EntradaReporteDistributivo(
            pao_ids=(p1.id, p2.id),
            facultad_ids=(f1.id, f2.id),
        ),
        contexto_admin,
    )

    assert vista.periodos == ["2025-2 GRADO", "2026-1 GRADO"]
    assert vista.facultades == ["FCID", "FCSEE"]

    filtro = uow.distributivo.ultimo_filtro
    assert filtro.pao_ids == (p1.id, p2.id)
    assert filtro.facultad_ids == (f1.id, f2.id)


async def test_el_reporte_exige_al_menos_un_periodo(contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Sin periodo saldria el historico entero, que nadie quiere por accidente."""
    from app.application.casos_uso.reporte_distributivo import (
        EntradaReporteDistributivo,
        VistaPreviaReporteDistributivo,
    )

    uow = _UowConCatalogos([])
    with pytest.raises(ErrorValidacion, match="periodo"):
        await VistaPreviaReporteDistributivo(uow, _RelojFijo())(  # type: ignore[arg-type]
            EntradaReporteDistributivo(), contexto_admin
        )


async def test_un_identificador_inexistente_corta_el_reporte(contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """Devolver menos filas en silencio daria un reporte incompleto."""
    from uuid import uuid4

    from app.application.casos_uso.reporte_distributivo import (
        EntradaReporteDistributivo,
        VistaPreviaReporteDistributivo,
    )
    from app.domain.entities.catalogo import TipoCatalogo
    from app.domain.errors import NoEncontrado

    pao = _catalogo(TipoCatalogo.PAO, "2026-1")
    uow = _UowConCatalogos([pao])

    with pytest.raises(NoEncontrado):
        await VistaPreviaReporteDistributivo(uow, _RelojFijo())(  # type: ignore[arg-type]
            EntradaReporteDistributivo(pao_ids=(pao.id,), facultad_ids=(uuid4(),)),
            contexto_admin,
        )


# ===========================================================================
# Relacion facultad -> carrera
# ===========================================================================


async def test_las_carreras_disponibles_salen_de_los_datos(uow, contexto_admin) -> None:  # type: ignore[no-untyped-def]
    """La relacion no vive en una columna: se deriva de las filas.

    Doce carreras se dictan en dos facultades a la vez —la facultad y la unidad
    en linea—, asi que un `facultad_id` en el catalogo se equivocaria en una de
    las dos.
    """
    from app.application.casos_uso.reporte_distributivo import (
        CarrerasDisponibles,
        EntradaCarrerasDisponibles,
    )
    from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo

    uow.distributivo.carreras = [
        ElementoCatalogo(tipo=TipoCatalogo.CARRERA, codigo="SOFTWARE", nombre="Software")
    ]
    pao, facultad = uuid4(), uuid4()

    carreras = await CarrerasDisponibles(uow)(
        EntradaCarrerasDisponibles(pao_ids=(pao,), facultad_ids=(facultad,)),
        contexto_admin,
    )

    assert [c.nombre for c in carreras] == ["SOFTWARE"]
    # El filtro llega entero: lo ofrecido coincide con lo que saldra despues.
    assert uow.distributivo.ultimo_filtro.pao_ids == (pao,)
    assert uow.distributivo.ultimo_filtro.facultad_ids == (facultad,)


async def test_las_carreras_disponibles_respetan_el_alcance(uow, roles) -> None:  # type: ignore[no-untyped-def]
    from tests.conftest import hacer_usuario

    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.reporte_distributivo import (
        CarrerasDisponibles,
        EntradaCarrerasDisponibles,
    )
    from app.domain.enums import RolCodigo

    usuario = hacer_usuario(roles={roles[RolCodigo.COORDINADOR.value]})
    facultad_propia = uuid4()
    usuario.definir_alcance([facultad_propia], [])

    await CarrerasDisponibles(uow)(
        EntradaCarrerasDisponibles(pao_ids=(uuid4(),)),
        ContextoEjecucion(actor=usuario),
    )

    assert uow.distributivo.ultimo_filtro.alcance.facultades == {facultad_propia}
