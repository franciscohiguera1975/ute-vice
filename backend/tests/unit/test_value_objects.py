"""Pruebas de los objetos de valor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.errors import ErrorValidacion
from app.domain.value_objects import (
    Cedula,
    ContrasenaEnClaro,
    Email,
    NombrePersona,
    PeriodoCobertura,
    normalizar_texto,
)

pytestmark = pytest.mark.unit


class TestCedula:
    """La cedula se valida con el algoritmo de modulo 10 del Registro Civil.

    Importa mas de lo que parece: una cedula invalida que llegue al proveedor
    externo consume presupuesto de consultas y produce un error que hay que
    diagnosticar. Filtrarla aqui es gratis.
    """

    @pytest.mark.parametrize(
        "valor",
        ["1710034065", "1713175477", "0926687856", "1104537772", "1802345676"],
    )
    def test_acepta_cedulas_con_verificador_correcto(self, valor: str) -> None:
        assert Cedula(valor).valor == valor

    def test_normaliza_separadores(self) -> None:
        assert Cedula("171-003-4065").valor == "1710034065"
        assert Cedula(" 1710034065 ").valor == "1710034065"

    def test_rechaza_digito_verificador_incorrecto(self) -> None:
        with pytest.raises(ErrorValidacion, match="digito verificador"):
            Cedula("1710034066")

    def test_rechaza_longitud_incorrecta(self) -> None:
        with pytest.raises(ErrorValidacion, match="10 digitos"):
            Cedula("171003406")

    def test_rechaza_provincia_inexistente(self) -> None:
        with pytest.raises(ErrorValidacion, match="provincia"):
            Cedula("9910034065")

    def test_rechaza_cedulas_que_no_son_de_persona_natural(self) -> None:
        """El tercer digito >= 6 identifica entidades publicas y sociedades."""
        with pytest.raises(ErrorValidacion, match="persona natural"):
            Cedula("1760034065")

    def test_rechaza_texto_no_numerico(self) -> None:
        with pytest.raises(ErrorValidacion, match="digitos"):
            Cedula("17100340AB")

    def test_es_valida_no_lanza(self) -> None:
        assert Cedula.es_valida("1710034065") is True
        assert Cedula.es_valida("1710034066") is False
        assert Cedula.es_valida("") is False

    def test_enmascarada_oculta_el_centro(self) -> None:
        assert Cedula("1710034065").enmascarada() == "17******65"

    def test_es_comparable_por_valor(self) -> None:
        assert Cedula("1710034065") == Cedula("171-003-4065")
        assert len({Cedula("1710034065"), Cedula("1710034065")}) == 1


class TestEmail:
    def test_normaliza_a_minusculas(self) -> None:
        assert Email("  Ana.Yepez@UTE.edu.EC ").valor == "ana.yepez@ute.edu.ec"

    def test_expone_usuario_y_dominio(self) -> None:
        email = Email("ana.yepez@ute.edu.ec")
        assert email.usuario == "ana.yepez"
        assert email.dominio == "ute.edu.ec"

    @pytest.mark.parametrize("valor", ["", "sin-arroba", "a@b", "@ute.edu.ec", "a b@ute.ec"])
    def test_rechaza_correos_invalidos(self, valor: str) -> None:
        with pytest.raises(ErrorValidacion):
            Email(valor)

    def test_reconoce_dominio_institucional(self) -> None:
        assert Email("a@ute.edu.ec").es_institucional(frozenset({"ute.edu.ec"}))
        assert not Email("a@gmail.com").es_institucional(frozenset({"ute.edu.ec"}))


class TestContrasenaEnClaro:
    def test_acepta_una_contrasena_conforme(self) -> None:
        assert ContrasenaEnClaro("Segura#2026.Ok").valor == "Segura#2026.Ok"

    @pytest.mark.parametrize(
        ("valor", "motivo"),
        [
            ("Corta#1a", "al menos"),
            ("minusculas#2026", "mayuscula"),
            ("MAYUSCULAS#2026", "minuscula"),
            ("SinDigitos#abc", "digito"),
            ("SinEspecial2026x", "especial"),
            ("Password#2026aa", "comun"),
            ("Abc123456#Xyz", "comun"),
        ],
    )
    def test_rechaza_contrasenas_debiles(self, valor: str, motivo: str) -> None:
        with pytest.raises(ErrorValidacion, match=motivo):
            ContrasenaEnClaro(valor)

    def test_no_expone_el_valor_en_su_representacion(self) -> None:
        """El valor no debe aparecer en trazas ni en volcados de depuracion."""
        secreta = ContrasenaEnClaro("Segura#2026.Ok")
        assert "Segura" not in repr(secreta)
        assert "Segura" not in str(secreta)


class TestNombrePersona:
    def test_normaliza_espacios_y_capitalizacion(self) -> None:
        nombre = NombrePersona(nombres="  ana   maria ", apellidos="yepez  cordova")
        assert nombre.nombres == "Ana Maria"
        assert nombre.apellidos == "Yepez Cordova"

    def test_ofrece_orden_formal_para_listados(self) -> None:
        nombre = NombrePersona(nombres="Ana Maria", apellidos="Yepez Cordova")
        assert nombre.completo == "Ana Maria Yepez Cordova"
        assert nombre.formal == "Yepez Cordova, Ana Maria"

    def test_normalizado_elimina_acentos(self) -> None:
        nombre = NombrePersona(nombres="José", apellidos="Muñoz Peña")
        assert nombre.normalizado == "jose munoz pena"

    @pytest.mark.parametrize(("n", "a"), [("", "Yepez"), ("Ana", ""), ("  ", "Yepez")])
    def test_exige_nombres_y_apellidos(self, n: str, a: str) -> None:
        with pytest.raises(ErrorValidacion):
            NombrePersona(nombres=n, apellidos=a)


class TestNormalizarTexto:
    """La normalizacion evita cambios falsos al reconciliar.

    El proveedor externo devuelve el mismo titulo con acentuacion y espaciado
    inconsistentes entre consultas. Sin normalizar, cada consulta reportaria una
    modificacion inexistente y el historico se llenaria de ruido.
    """

    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("INGENIERÍA  EN   SISTEMAS", "ingenieria en sistemas"),
            ("Ingenieria en Sistemas", "ingenieria en sistemas"),
            ("  MÉDICO CIRUJANO  ", "medico cirujano"),
            ("", ""),
        ],
    )
    def test_normaliza(self, entrada: str, esperado: str) -> None:
        assert normalizar_texto(entrada) == esperado


class TestPeriodoCobertura:
    def test_construye_desde_una_duracion(self) -> None:
        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        periodo = PeriodoCobertura.desde(inicio, dias=90)
        assert periodo.dias == 90
        assert periodo.fin == inicio + timedelta(days=90)

    def test_contiene_solo_dentro_del_rango(self) -> None:
        periodo = PeriodoCobertura.desde(datetime(2026, 1, 1, tzinfo=UTC), dias=30)
        assert periodo.contiene(datetime(2026, 1, 15, tzinfo=UTC))
        assert not periodo.contiene(datetime(2025, 12, 31, tzinfo=UTC))
        assert not periodo.contiene(datetime(2026, 2, 15, tzinfo=UTC))

    def test_progreso_esta_acotado_entre_cero_y_uno(self) -> None:
        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        periodo = PeriodoCobertura.desde(inicio, dias=100)
        assert periodo.progreso(inicio) == 0.0
        assert periodo.progreso(inicio + timedelta(days=50)) == pytest.approx(0.5)
        assert periodo.progreso(inicio + timedelta(days=500)) == 1.0
        assert periodo.progreso(inicio - timedelta(days=10)) == 0.0

    def test_exige_fechas_con_zona_horaria(self) -> None:
        with pytest.raises(ErrorValidacion, match="zona horaria"):
            PeriodoCobertura(inicio=datetime(2026, 1, 1), fin=datetime(2026, 2, 1))

    def test_exige_inicio_anterior_al_fin(self) -> None:
        momento = datetime(2026, 1, 1, tzinfo=UTC)
        with pytest.raises(ErrorValidacion, match="anterior"):
            PeriodoCobertura(inicio=momento, fin=momento)
