"""Pruebas de la lectura de configuracion desde el entorno.

Estas pruebas existen por un fallo concreto: el formato de `CORS_ORIGINS`
documentado en `.env.example` —una lista separada por comas— abortaba el
arranque, porque pydantic intentaba interpretarlo como JSON antes de que
corriera el validador. Un error asi no se manifiesta hasta el primer despliegue
real, que es el peor momento posible.
"""

from __future__ import annotations

import pytest

from app.core.config import Environment, get_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _limpiar_cache():  # type: ignore[no-untyped-def]
    """La configuracion se cachea por proceso: se limpia entre pruebas."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestListasEnVariablesDeEntorno:
    def test_acepta_el_formato_documentado_separado_por_comas(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200")
        assert get_settings().cors_origins == [
            "http://localhost:4200",
            "http://127.0.0.1:4200",
        ]

    def test_acepta_un_unico_valor(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:4200")
        assert get_settings().cors_origins == ["http://localhost:4200"]

    def test_acepta_una_lista_json(self, monkeypatch) -> None:
        """Algunos orquestadores inyectan las listas en formato JSON."""
        monkeypatch.setenv("CORS_ORIGINS", '["http://a.ute.edu.ec","http://b.ute.edu.ec"]')
        assert get_settings().cors_origins == ["http://a.ute.edu.ec", "http://b.ute.edu.ec"]

    def test_ignora_espacios_sobrantes(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", " http://a.ec , http://b.ec ,, ")
        assert get_settings().cors_origins == ["http://a.ec", "http://b.ec"]

    def test_sin_definir_usa_el_valor_por_defecto(self, monkeypatch) -> None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        assert get_settings().cors_origins == ["http://localhost:4200"]

    def test_json_malformado_falla_con_un_mensaje_util(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", '["sin cerrar"')
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            get_settings()


class TestSeccionesAnidadas:
    def test_construye_el_dsn_de_la_base(self, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_HOST", "bd.interno")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DB", "ute_prod")
        monkeypatch.setenv("POSTGRES_USER", "ute")
        monkeypatch.setenv("POSTGRES_PASSWORD", "secreta")

        dsn = get_settings().db.async_dsn
        assert dsn.startswith("postgresql+asyncpg://")
        assert "bd.interno:5433" in dsn
        assert "ute_prod" in dsn

    def test_el_secreto_se_comparte_con_la_seccion_jwt(self, monkeypatch) -> None:
        """El token se firma con el mismo secreto raiz: no son dos claves."""
        monkeypatch.setenv("SECRET_KEY", "x" * 64)
        settings = get_settings()
        assert settings.jwt.secret_key == settings.secret_key

    def test_las_franjas_horarias_se_leen_como_enteros(self, monkeypatch) -> None:
        monkeypatch.setenv("SCHEDULER_PEAK_START_HOUR", "7")
        monkeypatch.setenv("SCHEDULER_PEAK_END_HOUR", "16")
        monkeypatch.setenv("SCHEDULER_OFFPEAK_END_HOUR", "20")

        planificador = get_settings().scheduler
        assert (planificador.peak_start_hour, planificador.peak_end_hour) == (7, 16)
        assert planificador.offpeak_end_hour == 20

    def test_rechaza_franjas_incoherentes(self, monkeypatch) -> None:
        monkeypatch.setenv("SCHEDULER_PEAK_START_HOUR", "18")
        monkeypatch.setenv("SCHEDULER_PEAK_END_HOUR", "9")
        with pytest.raises(ValueError, match="PEAK_START"):
            get_settings()

    def test_google_exige_credenciales_si_esta_habilitado(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "true")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
            get_settings()

    def test_el_proveedor_oficial_exige_su_url(self, monkeypatch) -> None:
        monkeypatch.setenv("SENESCYT_PROVIDER", "oficial")
        monkeypatch.delenv("SENESCYT_OFICIAL_API_URL", raising=False)
        with pytest.raises(ValueError, match="convenio"):
            get_settings()


class TestCerrojoDeProduccion:
    """En produccion, arrancar con valores de ejemplo debe ser imposible."""

    @pytest.fixture(autouse=True)
    def _entorno_produccion(self, monkeypatch):  # type: ignore[no-untyped-def]
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("SECRET_KEY", "s" * 64)
        monkeypatch.setenv("POSTGRES_PASSWORD", "una-contrasena-real")
        monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", "Real#2026.Segura")
        monkeypatch.setenv("CORS_ORIGINS", "https://vice.ute.edu.ec")

    def test_una_configuracion_correcta_arranca(self) -> None:
        settings = get_settings()
        assert settings.environment is Environment.PRODUCTION

    def test_rechaza_el_secreto_de_ejemplo(self, monkeypatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "cambiame_por_una_clave_larga_y_aleatoria")
        with pytest.raises(ValueError, match="SECRET_KEY"):
            get_settings()

    def test_rechaza_un_secreto_demasiado_corto(self, monkeypatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "corto")
        with pytest.raises(ValueError, match="SECRET_KEY"):
            get_settings()

    def test_rechaza_la_contrasena_de_base_de_ejemplo(self, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_PASSWORD", "cambiame_en_produccion")
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            get_settings()

    def test_rechaza_la_contrasena_de_superusuario_de_ejemplo(self, monkeypatch) -> None:
        monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", "UteVice#2026.Inicial")
        with pytest.raises(ValueError, match="FIRST_SUPERUSER_PASSWORD"):
            get_settings()

    def test_rechaza_el_modo_depuracion(self, monkeypatch) -> None:
        monkeypatch.setenv("DEBUG", "true")
        with pytest.raises(ValueError, match="DEBUG"):
            get_settings()

    def test_rechaza_un_origen_cors_sin_cifrar(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://vice.ute.edu.ec")
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            get_settings()

    def test_permite_localhost_sin_cifrar(self, monkeypatch) -> None:
        """Util para diagnosticar contra un despliegue de produccion local."""
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:4200")
        assert get_settings().environment is Environment.PRODUCTION
