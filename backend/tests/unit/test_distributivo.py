"""Pruebas del dominio del distributivo docente."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import (
    Docente,
    FilaDistributivo,
    clasificar_periodo,
    separar_titulos,
)
from app.domain.errors import ErrorValidacion
from app.domain.value_objects_distributivo import (
    DistribucionHoras,
    Identificacion,
    NivelPeriodo,
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
    """Un semestre son tres periodos: tecnologia, grado y posgrado."""

    def test_arma_el_codigo_institucional(self) -> None:
        """`2 6 | 1 | 65 | 1`: anio, periodo del anio, nivel y una constante."""
        assert PeriodoAcademico(2026, 1, NivelPeriodo.TECNOLOGIA).codigo == "261151"
        assert PeriodoAcademico(2026, 1, NivelPeriodo.GRADO).codigo == "261651"
        assert PeriodoAcademico(2026, 1, NivelPeriodo.POSGRADO).codigo == "261751"
        assert PeriodoAcademico(2023, 2, NivelPeriodo.POSGRADO).codigo == "232751"

    def test_interpreta_el_codigo_institucional(self) -> None:
        pao = PeriodoAcademico.desde_codigo("261751")
        assert (pao.anio, pao.periodo, pao.nivel) == (2026, 1, NivelPeriodo.POSGRADO)
        assert pao.nombre == "2026-1 POSGRADO"
        assert pao.semestre == "2026-1"

    def test_admite_el_semestre_suelto(self) -> None:
        """Es como viene el PAO en el consolidado; el nivel sale de la fila."""
        pao = PeriodoAcademico.desde_codigo("2026-1")
        assert (pao.anio, pao.periodo) == (2026, 1)
        assert pao.nivel is NivelPeriodo.GRADO

    def test_tolera_espacios(self) -> None:
        assert PeriodoAcademico.desde_codigo(" 2026 - 1 ").semestre == "2026-1"
        assert PeriodoAcademico.desde_codigo(" 261651 ").codigo == "261651"

    @pytest.mark.parametrize(
        # `261650` ya no esta aqui: el ultimo digito distingue el interciclo
        # (`0`) del ordinario (`1`), asi que es un codigo valido.
        "codigo",
        ["2026", "2026-3", "26-1", "", "abc", "2026/1", "261951", "261652"],
    )
    def test_rechaza_codigos_invalidos(self, codigo: str) -> None:
        with pytest.raises(ErrorValidacion, match="PAO"):
            PeriodoAcademico.desde_codigo(codigo)

    def test_el_ultimo_digito_marca_el_interciclo(self) -> None:
        ordinario = PeriodoAcademico.desde_codigo("261651")
        corto = PeriodoAcademico.desde_codigo("261650")

        assert ordinario.interciclo is False
        assert corto.interciclo is True
        assert corto.nombre == "2026-1 GRADO INTERCICLO"
        # Comparten semestre y nivel: son dos periodos del mismo momento.
        assert (corto.anio, corto.periodo, corto.nivel) == (
            ordinario.anio,
            ordinario.periodo,
            ordinario.nivel,
        )

    def test_se_ordena_cronologicamente(self) -> None:
        """Ordenar por texto acertaria por casualidad; el reporte deriva de aqui
        el anio de inicio de un docente en una carrera."""
        codigos = ["261651", "202651", "251651", "201651", "252651"]
        periodos = sorted(PeriodoAcademico.desde_codigo(c) for c in codigos)
        assert [p.nombre for p in periodos] == [
            "2020-1 GRADO",
            "2020-2 GRADO",
            "2025-1 GRADO",
            "2025-2 GRADO",
            "2026-1 GRADO",
        ]

    def test_los_tres_niveles_comparten_orden(self) -> None:
        """A proposito: el reporte deriva el anio dividiendo `orden` entre diez.

        Si el nivel entrara en `orden`, esa division dejaria de dar el anio.
        Para desempatar entre los tres se ordena despues por codigo.
        """
        ordenes = {PeriodoAcademico(2026, 1, n).orden for n in NivelPeriodo}
        assert ordenes == {20261}

    def test_el_orden_es_numerico(self) -> None:
        assert PeriodoAcademico.desde_codigo("261651").orden == 20261


class TestClasificacionDePeriodo:
    """A cual de los tres periodos del semestre va cada fila."""

    def test_la_facultad_tecnologica_manda_sobre_el_nivel(self) -> None:
        """Esas unidades imparten tecnologia aunque la fila diga grado."""
        assert clasificar_periodo("ETECH", "GRADO", None) is NivelPeriodo.TECNOLOGIA
        assert clasificar_periodo("UAEFTT", None, None) is NivelPeriodo.TECNOLOGIA

    @pytest.mark.parametrize(
        ("nivel", "esperado"),
        [("GRADO", NivelPeriodo.GRADO), ("POSGRADO", NivelPeriodo.POSGRADO)],
    )
    def test_fuera_de_esas_facultades_manda_el_nivel(self, nivel, esperado) -> None:  # type: ignore[no-untyped-def]
        assert clasificar_periodo("FCII", nivel, None) is esperado

    def test_sin_nivel_lo_toma_del_nombre_de_la_carrera(self) -> None:
        """Pasa en todo 2026-1: 731 filas llegan sin la columna NIVEL."""
        assert (
            clasificar_periodo("FCII", None, "UIO:MEDICINA VETERINARIA - GRADO - PRESENCIAL")
            is NivelPeriodo.GRADO
        )
        assert (
            clasificar_periodo("PEL", None, "UIO:URBANISMO - POSGRADO - EN LÍNEA")
            is NivelPeriodo.POSGRADO
        )

    def test_no_busca_la_palabra_suelta_en_todo_el_nombre(self) -> None:
        """El origen tiene 98 carreras de grado que mencionan «MAESTRIA»."""
        assert (
            clasificar_periodo("FCII", None, "MAESTRIA EN TURISMO, MENCION GESTION")
            is NivelPeriodo.GRADO
        )

    def test_sin_nivel_ni_pista_asume_grado(self) -> None:
        assert clasificar_periodo("FCII", None, None) is NivelPeriodo.GRADO


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
        assert elemento.nombre == "MONJAS"

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
        assert elemento.nombre == "MEDICINA GENERAL"
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
        fila.definir_asignaturas([uuid4()])
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

    def test_una_fila_admite_varias_asignaturas(self, fila: FilaDistributivo) -> None:
        """Un docente dicta mas de una materia en la misma carrera y periodo."""
        a, b = uuid4(), uuid4()
        fila.definir_asignaturas([a, b])
        assert fila.asignaturas_ids == [a, b]
        assert not fila.requiere_asignatura

    def test_definir_asignaturas_conserva_el_orden_y_descarta_repetidas(
        self, fila: FilaDistributivo
    ) -> None:
        """El orden es el que se escribio, y es el que sale en el reporte."""
        a, b = uuid4(), uuid4()
        fila.definir_asignaturas([b, a, b])
        assert fila.asignaturas_ids == [b, a]

    def test_una_lista_vacia_retira_todas(self, fila: FilaDistributivo) -> None:
        """`actualizar` no puede hacerlo: alli lo ausente significa «no cambies»."""
        fila.definir_asignaturas([uuid4()])
        fila.definir_asignaturas([])
        assert fila.asignaturas_ids == []
        assert fila.requiere_asignatura

    def test_actualizar_no_retira_las_asignaturas(self, fila: FilaDistributivo) -> None:
        asignatura = uuid4()
        fila.definir_asignaturas([asignatura])
        fila.actualizar(medida="NO APLICA")
        assert fila.asignaturas_ids == [asignatura]

    def test_actualizar_recalcula_los_totales(self, fila: FilaDistributivo) -> None:
        fila.actualizar(horas=DistribucionHoras.desde_plano({"Da": 1.0}))
        assert fila.total_horas == 1.0
