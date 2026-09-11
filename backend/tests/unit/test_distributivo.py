"""Pruebas del dominio del distributivo docente."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import (
    Docente,
    FilaDistributivo,
    separar_titulos,
)
from app.domain.errors import ErrorValidacion
from app.domain.value_objects_distributivo import (
    DistribucionHoras,
    Identificacion,
    PeriodoAcademico,
)

pytestmark = pytest.mark.unit


class TestIdentificacion:
    """El padron docente incluye extranjeros, asi que no basta con `Cedula`."""

    def test_reconoce_una_cedula_valida(self) -> None:
        identificacion = Identificacion("1710034065")
        assert identificacion.es_cedula
        assert identificacion.valor == "1710034065"

    def test_normaliza_separadores_y_mayusculas(self) -> None:
        assert Identificacion("171-003.4065").valor == "1710034065"
        assert Identificacion("ar920756").valor == "AR920756"

    @pytest.mark.parametrize("pasaporte", ["AR920756", "G04590632", "AAJ349755", "048904925W"])
    def test_acepta_pasaportes(self, pasaporte: str) -> None:
        """Sin esto quedarian fuera 149 docentes reales del consolidado."""
        identificacion = Identificacion(pasaporte)
        assert not identificacion.es_cedula
        assert identificacion.valor == pasaporte.upper()

    @pytest.mark.parametrize("valor", ["", "  ", "AB", "06452930/5", "x" * 21])
    def test_rechaza_documentos_imposibles(self, valor: str) -> None:
        with pytest.raises(ErrorValidacion):
            Identificacion(valor)

    def test_es_valida_no_lanza(self) -> None:
        assert Identificacion.es_valida("AR920756")
        assert not Identificacion.es_valida("06452930/5")

    def test_enmascarada_oculta_el_centro(self) -> None:
        assert Identificacion("1710034065").enmascarada() == "17******65"


class TestPeriodoAcademico:
    def test_interpreta_el_codigo(self) -> None:
        pao = PeriodoAcademico.desde_codigo("2026-1")
        assert (pao.anio, pao.periodo) == (2026, 1)
        assert pao.codigo == "2026-1"

    def test_tolera_espacios(self) -> None:
        assert PeriodoAcademico.desde_codigo(" 2026 - 1 ").codigo == "2026-1"

    @pytest.mark.parametrize("codigo", ["2026", "2026-3", "26-1", "", "abc", "2026/1"])
    def test_rechaza_codigos_invalidos(self, codigo: str) -> None:
        with pytest.raises(ErrorValidacion, match="PAO"):
            PeriodoAcademico.desde_codigo(codigo)

    def test_se_ordena_cronologicamente(self) -> None:
        """Ordenar por texto acertaria por casualidad; el reporte deriva de aqui
        el anio de inicio de un docente en una carrera."""
        codigos = ["2026-1", "2020-2", "2025-1", "2020-1", "2025-2"]
        periodos = sorted(PeriodoAcademico.desde_codigo(c) for c in codigos)
        assert [p.codigo for p in periodos] == [
            "2020-1",
            "2020-2",
            "2025-1",
            "2025-2",
            "2026-1",
        ]

    def test_el_orden_es_numerico(self) -> None:
        assert PeriodoAcademico.desde_codigo("2026-1").orden == 20261


class TestDistribucionHoras:
    def test_suma_cada_bloque_por_separado(self) -> None:
        horas = DistribucionHoras.desde_plano(
            {"Da": 9.0, "Db": 2.5, "Ga": 1.0, "Ic": 0.5, "Va": 0.25}
        )
        assert horas.total_docencia == 11.5
        assert horas.total_gestion == 1.0
        assert horas.total_investigacion == 0.5
        assert horas.total_vinculacion == 0.25
        assert horas.total == 13.25

    def test_omite_los_valores_ausentes(self) -> None:
        """El origen distingue «no aplica» (celda vacia) de «cero horas»."""
        horas = DistribucionHoras.desde_plano({"Da": 1.0, "Db": None, "Dc": 0.0})
        assert "Db" not in horas.docencia
        assert horas.docencia["Dc"] == 0.0

    def test_usa_redondeo_bancario(self) -> None:
        """El consolidado se construyo con el redondeo de R y Python.

        Con HALF_UP el total diferiria en un centesimo del archivo de origen, y
        esa diferencia se lee como un error de carga.
        """
        assert DistribucionHoras.desde_plano({"Da": 0.125, "Db": 0.0}).total == 0.12
        assert DistribucionHoras.desde_plano({"Da": 0.135, "Db": 0.0}).total == 0.14

    def test_una_distribucion_vacia_totaliza_cero(self) -> None:
        vacia = DistribucionHoras.vacia()
        assert vacia.esta_vacia
        assert vacia.total == 0.0

    def test_vuelve_al_diccionario_plano(self) -> None:
        plano = {"Da": 1.0, "Ga": 2.0, "Ic": 3.0, "Va": 4.0}
        assert DistribucionHoras.desde_plano(plano).a_plano() == plano


class TestSepararTitulos:
    """El consolidado concatena hasta doce titulos en una sola celda."""

    def test_separa_por_ampersand(self) -> None:
        assert separar_titulos("ARQUITECTO & MAGISTER EN URBANISMO") == [
            "ARQUITECTO",
            "MAGISTER EN URBANISMO",
        ]

    def test_separa_por_coma_con_espacio(self) -> None:
        """El origen usa la coma con espaciado inconsistente."""
        esperado = ["ABOGADO", "DOCTOR EN JURISPRUDENCIA"]
        assert separar_titulos("ABOGADO , DOCTOR EN JURISPRUDENCIA") == esperado
        assert separar_titulos("ABOGADO ,DOCTOR EN JURISPRUDENCIA") == esperado
        assert separar_titulos("ABOGADO, DOCTOR EN JURISPRUDENCIA") == esperado

    def test_combina_ambos_separadores(self) -> None:
        assert separar_titulos("A & B , C") == ["A", "B", "C"]

    def test_descarta_duplicados_conservando_el_orden(self) -> None:
        assert separar_titulos("ARQUITECTO & ARQUITECTO & INGENIERO") == [
            "ARQUITECTO",
            "INGENIERO",
        ]

    def test_descarta_los_marcadores_de_ausencia(self) -> None:
        assert separar_titulos("NA") == []
        assert separar_titulos("ARQUITECTO & NA & -") == ["ARQUITECTO"]

    @pytest.mark.parametrize("vacio", [None, "", "   "])
    def test_una_celda_vacia_no_produce_titulos(self, vacio: str | None) -> None:
        assert separar_titulos(vacio) == []

    def test_normaliza_espacios_y_mayusculas(self) -> None:
        assert separar_titulos("  arquitecto   urbano  ") == ["ARQUITECTO URBANO"]


class TestElementoCatalogo:
    def test_normaliza_el_codigo_a_mayusculas(self) -> None:
        elemento = ElementoCatalogo(tipo=TipoCatalogo.SEDE, codigo="  mon ", nombre="  Monjas  ")
        assert elemento.codigo == "MON"
        assert elemento.nombre == "Monjas"

    def test_el_pao_deriva_anio_periodo_y_orden_del_codigo(self) -> None:
        """Asi ordenar por periodo no depende de comparar cadenas."""
        pao = ElementoCatalogo(tipo=TipoCatalogo.PAO, codigo="2026-1", nombre="PAO 2026-1")
        assert pao.atributos["anio"] == 2026
        assert pao.atributos["periodo"] == 1
        assert pao.orden == 20261

    def test_un_pao_con_codigo_invalido_se_rechaza(self) -> None:
        with pytest.raises(ErrorValidacion, match="PAO"):
            ElementoCatalogo(tipo=TipoCatalogo.PAO, codigo="2026", nombre="x")

    def test_actualizar_no_toca_el_codigo(self) -> None:
        """El codigo es la identidad del elemento y hay filas apuntando a el."""
        elemento = ElementoCatalogo(tipo=TipoCatalogo.CARRERA, codigo="MEDICINA", nombre="Medicina")
        elemento.actualizar(nombre="Medicina General", activo=False)
        assert elemento.codigo == "MEDICINA"
        assert elemento.nombre == "Medicina General"
        assert not elemento.activo

    def test_la_clave_de_busqueda_ignora_acentos(self) -> None:
        elemento = ElementoCatalogo(
            tipo=TipoCatalogo.CARRERA, codigo="PEDAGOGÍA", nombre="Pedagogía"
        )
        assert "pedagogia" in elemento.clave_busqueda

    @pytest.mark.parametrize(("codigo", "nombre"), [("", "x"), ("x", ""), ("x" * 321, "x")])
    def test_rechaza_codigos_y_nombres_invalidos(self, codigo: str, nombre: str) -> None:
        with pytest.raises(ErrorValidacion):
            ElementoCatalogo(tipo=TipoCatalogo.SEDE, codigo=codigo, nombre=nombre)

    def test_los_doce_catalogos_tienen_etiqueta(self) -> None:
        for tipo in TipoCatalogo:
            assert tipo.etiqueta and tipo.singular


class TestDocente:
    def test_normaliza_el_nombre(self) -> None:
        docente = Docente(
            identificacion=Identificacion("1710034065"),
            nombre_completo="  perez   gomez  juan ",
        )
        assert docente.nombre_completo == "PEREZ GOMEZ JUAN"

    def test_sabe_si_es_contrastable_con_el_registro(self) -> None:
        """Un docente con pasaporte no tiene cedula que consultar al SENESCYT."""
        assert Docente(
            identificacion=Identificacion("1710034065"), nombre_completo="X Y"
        ).puede_validarse_en_registro
        assert not Docente(
            identificacion=Identificacion("AR920756"), nombre_completo="X Y"
        ).puede_validarse_en_registro

    def test_los_titulos_no_se_repiten_y_conservan_el_orden(self) -> None:
        from uuid import uuid4

        a, b = uuid4(), uuid4()
        docente = Docente(identificacion=Identificacion("1710034065"), nombre_completo="X Y")
        docente.establecer_titulos([a, b, a])
        assert docente.titulos_ids == [a, b]

    def test_exige_nombre(self) -> None:
        with pytest.raises(ErrorValidacion, match="nombre"):
            Docente(identificacion=Identificacion("1710034065"), nombre_completo="   ")


class TestFilaDistributivo:
    @pytest.fixture
    def fila(self):  # type: ignore[no-untyped-def]
        from uuid import uuid4

        return FilaDistributivo(
            docente_id=uuid4(),
            pao_id=uuid4(),
            facultad_id=uuid4(),
            carrera_id=uuid4(),
            horas=DistribucionHoras.desde_plano({"Da": 9.0, "Db": 2.5}),
        )

    def test_el_total_sale_de_la_distribucion(self, fila: FilaDistributivo) -> None:
        assert fila.total_horas == 11.5
        assert fila.tiene_carga

    def test_senala_las_filas_con_docencia_pero_sin_asignatura(
        self, fila: FilaDistributivo
    ) -> None:
        """Es lo que el reporte institucional deja en blanco."""
        assert fila.requiere_asignatura
        fila.definir_asignatura(uuid4())
        assert not fila.requiere_asignatura

    def test_una_fila_sin_docencia_no_requiere_asignatura(self) -> None:
        from uuid import uuid4

        fila = FilaDistributivo(
            docente_id=uuid4(),
            pao_id=uuid4(),
            facultad_id=uuid4(),
            carrera_id=uuid4(),
            horas=DistribucionHoras.desde_plano({"Ga": 40.0}),
        )
        assert not fila.requiere_asignatura

    def test_definir_asignatura_con_none_la_retira(self, fila: FilaDistributivo) -> None:
        """`actualizar` no puede hacerlo: alli `None` significa «no cambies»."""
        asignatura = uuid4()
        fila.definir_asignatura(asignatura)
        assert fila.asignatura_id == asignatura

        fila.definir_asignatura(None)
        assert fila.asignatura_id is None
        assert fila.requiere_asignatura

    def test_actualizar_no_retira_la_asignatura(self, fila: FilaDistributivo) -> None:
        """Un `None` en `actualizar` deja el campo como estaba, no lo borra."""
        asignatura = uuid4()
        fila.definir_asignatura(asignatura)
        fila.actualizar(medida="NO APLICA")
        assert fila.asignatura_id == asignatura

    def test_actualizar_recalcula_los_totales(self, fila: FilaDistributivo) -> None:
        fila.actualizar(horas=DistribucionHoras.desde_plano({"Da": 1.0}))
        assert fila.total_horas == 1.0
