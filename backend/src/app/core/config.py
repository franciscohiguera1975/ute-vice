"""Configuracion tipada de la aplicacion.

Toda la configuracion entra por variables de entorno y se valida al arrancar:
si falta algo o esta mal formado, el proceso muere de inmediato con un mensaje
claro en lugar de fallar a mitad de una peticion.

Las secciones son objetos anidados (`settings.jwt.secret_key`) para que cada
adaptador reciba solo el trozo de configuracion que le concierne, en lugar de
un objeto global gigante — es interface segregation aplicado a la config.
"""

from __future__ import annotations

import secrets
from datetime import time
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    PostgresDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------

Hour = Annotated[int, Field(ge=0, le=23)]


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self is Environment.PRODUCTION


class SenescytProviderKind(StrEnum):
    """Implementacion del puerto `TitleLookupProvider` que se inyecta."""

    MOCK = "mock"
    """Datos sinteticos deterministas. Desarrollo y pruebas."""

    MANUAL = "manual"
    """Cola asistida: un operador humano resuelve el desafio en la interfaz."""

    OFICIAL = "oficial"
    """API institucional bajo convenio. Requiere URL y credencial."""


# ---------------------------------------------------------------------------
# Secciones
# ---------------------------------------------------------------------------


class DatabaseSettings(BaseModel):
    user: str = "ute"
    password: str = "ute"
    db: str = "ute_vice"
    host: str = "postgres"
    port: int = 5432

    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    pool_recycle_seconds: int = 1800
    echo_sql: bool = False

    @property
    def async_dsn(self) -> str:
        """DSN para SQLAlchemy asincrono (driver asyncpg)."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                path=self.db,
            )
        )

    @property
    def sync_dsn(self) -> str:
        """DSN sincrono. Lo usa Alembic, que no corre sobre el loop async."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg2",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                path=self.db,
            )
        )


class JWTSettings(BaseModel):
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    issuer: str = "ute-vice"
    audience: str = "ute-vice-api"


class GoogleOAuthSettings(BaseModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    allowed_domains: list[str] = Field(default_factory=lambda: ["ute.edu.ec"])
    default_role: str = "CONSULTA"

    # Endpoints de Google. Se dejan configurables para poder apuntar a un doble
    # de pruebas en los tests de integracion.
    authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"

    @model_validator(mode="after")
    def _validar_credenciales(self) -> GoogleOAuthSettings:
        if self.enabled and not (self.client_id and self.client_secret):
            raise ValueError(
                "GOOGLE_OAUTH_ENABLED=true exige GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET"
            )
        return self

    def dominio_permitido(self, email: str) -> bool:
        """Un dominio vacio en la lista significa 'sin restriccion'."""
        if not self.allowed_domains:
            return True
        dominio = email.rsplit("@", 1)[-1].lower()
        return dominio in {d.strip().lower() for d in self.allowed_domains if d.strip()}


class LDAPSettings(BaseModel):
    enabled: bool = False
    server_uri: str = "ldap://ad.ute.edu.ec:389"
    use_ssl: bool = False
    bind_dn: str = ""
    bind_password: str = ""
    user_search_base: str = ""
    user_filter: str = "(sAMAccountName={username})"
    attr_email: str = "mail"
    attr_full_name: str = "displayName"
    default_role: str = "CONSULTA"
    timeout_seconds: int = 10

    @model_validator(mode="after")
    def _validar(self) -> LDAPSettings:
        if self.enabled and not self.user_search_base:
            raise ValueError("LDAP_ENABLED=true exige LDAP_USER_SEARCH_BASE")
        if self.enabled and "{username}" not in self.user_filter:
            raise ValueError("LDAP_USER_FILTER debe contener el marcador {username}")
        return self


class SenescytSettings(BaseModel):
    provider: SenescytProviderKind = SenescytProviderKind.MOCK
    base_url: str = "https://www.senescyt.gob.ec"
    timeout_seconds: int = Field(default=30, ge=5, le=180)
    max_attempts: int = Field(default=3, ge=1, le=10)
    oficial_api_url: str = ""
    oficial_api_key: str = ""

    @model_validator(mode="after")
    def _validar_oficial(self) -> SenescytSettings:
        if self.provider is SenescytProviderKind.OFICIAL and not self.oficial_api_url:
            raise ValueError(
                "SENESCYT_PROVIDER=oficial exige SENESCYT_OFICIAL_API_URL. "
                "Este proveedor requiere convenio institucional vigente."
            )
        return self


class SchedulerSettings(BaseModel):
    """Politica de ritmo del planificador de consultas.

    El objetivo de estos parametros es *reducir* la carga que generamos sobre el
    proveedor y repartirla en el tiempo: un presupuesto por hora, una separacion
    aleatoria entre peticiones y una degradacion progresiva ante errores. No son
    parametros de evasion; el sistema se identifica siempre y respeta los cortes.
    """

    enabled: bool = False

    # Ventana de cobertura: una persona no se vuelve a consultar hasta que todo
    # el padron haya sido cubierto o hayan pasado estos dias.
    period_days: int = Field(default=90, ge=1, le=730)

    # Tope duro de peticiones por hora, independiente de cualquier otro calculo.
    max_requests_per_hour: int = Field(default=30, ge=1, le=600)

    # Perfil horario: mas actividad en horario de oficina, menos al caer la tarde,
    # nada fuera de esas franjas.
    peak_start_hour: Hour = 8
    peak_end_hour: Hour = 17
    offpeak_end_hour: Hour = 21
    peak_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    offpeak_weight: float = Field(default=0.35, ge=0.0, le=1.0)

    # Separacion aleatoria entre consultas consecutivas.
    min_delay_seconds: int = Field(default=45, ge=1)
    max_delay_seconds: int = Field(default=240, ge=1)

    # Retroceso exponencial ante fallos del proveedor.
    backoff_base_seconds: int = Field(default=300, ge=1)
    backoff_max_seconds: int = Field(default=7200, ge=1)

    # Cortacircuitos: N fallos consecutivos pausan el job.
    circuit_breaker_failures: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def _validar_ventanas(self) -> SchedulerSettings:
        if self.min_delay_seconds > self.max_delay_seconds:
            raise ValueError("SCHEDULER_MIN_DELAY_SECONDS no puede superar a MAX")
        if not self.peak_start_hour < self.peak_end_hour <= self.offpeak_end_hour:
            raise ValueError("Las franjas deben cumplir: PEAK_START < PEAK_END <= OFFPEAK_END")
        if self.backoff_base_seconds > self.backoff_max_seconds:
            raise ValueError("SCHEDULER_BACKOFF_BASE_SECONDS no puede superar a MAX")
        return self

    @property
    def peak_start(self) -> time:
        return time(hour=self.peak_start_hour)

    @property
    def peak_end(self) -> time:
        return time(hour=self.peak_end_hour)

    @property
    def offpeak_end(self) -> time:
        return time(hour=self.offpeak_end_hour)


class ReportSettings(BaseModel):
    output_dir: Path = Path("/app/storage/reports")
    max_rows: int = Field(default=100_000, ge=1)
    institution_name: str = "Universidad Tecnologica Equinoccial"
    institution_unit: str = "Vicerrectorado"


class SecuritySettings(BaseModel):
    password_min_length: int = Field(default=10, ge=8, le=128)
    max_failed_logins: int = Field(default=5, ge=1, le=50)
    lockout_minutes: int = Field(default=15, ge=1, le=1440)


# ---------------------------------------------------------------------------
# Settings raiz
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Configuracion completa. Se construye una sola vez por proceso."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "UTE Vice - Gestión Académica"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    tz: str = "America/Guayaquil"
    api_v1_prefix: str = "/api/v1"
    # `NoDecode` impide que pydantic-settings intente interpretar la variable
    # como JSON antes de que corra el validador de abajo. Sin el, el formato
    # documentado en `.env.example` —`a,b,c`— aborta el arranque con un error
    # de parseo, que es justo lo contrario de lo que se busca en una variable
    # pensada para que la edite operaciones.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4200"]
    )

    # --- Secreto raiz y superusuario inicial ---
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    first_superuser_email: str = "admin@ute.edu.ec"
    first_superuser_password: str = "UteVice#2026.Inicial"
    first_superuser_name: str = "Administrador del Sistema"

    # --- Secciones (poblado en el validador de abajo) ---
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    google: GoogleOAuthSettings = Field(default_factory=GoogleOAuthSettings)
    ldap: LDAPSettings = Field(default_factory=LDAPSettings)
    senescyt: SenescytSettings = Field(default_factory=SenescytSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    reports: ReportSettings = Field(default_factory=ReportSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Acepta `a,b,c` ademas de una lista JSON."""
        if isinstance(v, str) and not v.strip().startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _cerrojo_de_produccion(self) -> Settings:
        """Impide arrancar en produccion con valores de ejemplo."""
        if not self.environment.is_production:
            return self

        problemas: list[str] = []
        if "cambiame" in self.secret_key.lower() or len(self.secret_key) < 32:
            problemas.append("SECRET_KEY es de ejemplo o demasiado corto")
        if "cambiame" in self.db.password.lower():
            problemas.append("POSTGRES_PASSWORD es de ejemplo")
        if "utevice#2026" in self.first_superuser_password.lower():
            problemas.append("FIRST_SUPERUSER_PASSWORD es de ejemplo")
        if self.debug:
            problemas.append("DEBUG debe ser false en produccion")
        if any(o.startswith("http://") and "localhost" not in o for o in self.cors_origins):
            problemas.append("CORS_ORIGINS contiene un origen http:// no local")

        if problemas:
            raise ValueError(
                "Configuracion insegura para ENVIRONMENT=production:\n  - "
                + "\n  - ".join(problemas)
            )
        return self


# ---------------------------------------------------------------------------
# Construccion desde el entorno plano
# ---------------------------------------------------------------------------


def _build_settings() -> Settings:
    """Traduce el `.env` plano (POSTGRES_HOST, JWT_ALGORITHM, ...) a secciones.

    Se prefiere un `.env` plano y legible por operaciones antes que exigir el
    formato anidado `DB__HOST` de pydantic-settings.
    """
    import os

    def get(name: str, default: str = "") -> str:
        return os.getenv(name, default)

    def as_bool(name: str, default: bool = False) -> bool:
        return get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

    def as_int(name: str, default: int) -> int:
        raw = get(name).strip()
        return int(raw) if raw else default

    def as_float(name: str, default: float) -> float:
        raw = get(name).strip()
        return float(raw) if raw else default

    def as_list(name: str, default: list[str]) -> list[str]:
        """Acepta `a,b,c` y tambien una lista JSON.

        La forma separada por comas es la documentada porque es la comoda de
        editar en un `.env`; la JSON se admite porque es lo que producen algunos
        orquestadores al inyectar variables.
        """
        raw = get(name).strip()
        if not raw:
            return default
        if raw.startswith("["):
            import json

            try:
                cargado = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{name} parece JSON pero no es valido: {exc}") from exc
            if not isinstance(cargado, list):
                raise ValueError(f"{name} debe ser una lista")
            return [str(x).strip() for x in cargado if str(x).strip()]
        return [x.strip() for x in raw.split(",") if x.strip()]

    secret = get("SECRET_KEY") or secrets.token_urlsafe(64)

    return Settings(
        app_name=get("APP_NAME", "UTE Vice - Gestión Académica"),
        environment=Environment(get("ENVIRONMENT", "development")),
        debug=as_bool("DEBUG", True),
        log_level=get("LOG_LEVEL", "INFO"),
        tz=get("TZ", "America/Guayaquil"),
        api_v1_prefix=get("API_V1_PREFIX", "/api/v1"),
        cors_origins=as_list("CORS_ORIGINS", ["http://localhost:4200"]),
        secret_key=secret,
        first_superuser_email=get("FIRST_SUPERUSER_EMAIL", "admin@ute.edu.ec"),
        first_superuser_password=get("FIRST_SUPERUSER_PASSWORD", "UteVice#2026.Inicial"),
        first_superuser_name=get("FIRST_SUPERUSER_NAME", "Administrador del Sistema"),
        db=DatabaseSettings(
            user=get("POSTGRES_USER", "ute"),
            password=get("POSTGRES_PASSWORD", "ute"),
            db=get("POSTGRES_DB", "ute_vice"),
            host=get("POSTGRES_HOST", "postgres"),
            port=as_int("POSTGRES_PORT", 5432),
            echo_sql=as_bool("POSTGRES_ECHO", False),
        ),
        jwt=JWTSettings(
            secret_key=secret,
            algorithm=get("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=as_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30),
            refresh_token_expire_days=as_int("REFRESH_TOKEN_EXPIRE_DAYS", 7),
        ),
        google=GoogleOAuthSettings(
            enabled=as_bool("GOOGLE_OAUTH_ENABLED", False),
            client_id=get("GOOGLE_CLIENT_ID"),
            client_secret=get("GOOGLE_CLIENT_SECRET"),
            redirect_uri=get(
                "GOOGLE_REDIRECT_URI",
                "http://localhost:8000/api/v1/auth/google/callback",
            ),
            allowed_domains=as_list("GOOGLE_ALLOWED_DOMAINS", ["ute.edu.ec"]),
            default_role=get("GOOGLE_DEFAULT_ROLE", "CONSULTA"),
        ),
        ldap=LDAPSettings(
            enabled=as_bool("LDAP_ENABLED", False),
            server_uri=get("LDAP_SERVER_URI", "ldap://ad.ute.edu.ec:389"),
            use_ssl=as_bool("LDAP_USE_SSL", False),
            bind_dn=get("LDAP_BIND_DN"),
            bind_password=get("LDAP_BIND_PASSWORD"),
            user_search_base=get("LDAP_USER_SEARCH_BASE"),
            user_filter=get("LDAP_USER_FILTER", "(sAMAccountName={username})"),
            attr_email=get("LDAP_ATTR_EMAIL", "mail"),
            attr_full_name=get("LDAP_ATTR_FULL_NAME", "displayName"),
            default_role=get("LDAP_DEFAULT_ROLE", "CONSULTA"),
        ),
        senescyt=SenescytSettings(
            provider=SenescytProviderKind(get("SENESCYT_PROVIDER", "mock")),
            base_url=get("SENESCYT_BASE_URL", "https://www.senescyt.gob.ec"),
            timeout_seconds=as_int("SENESCYT_TIMEOUT_SECONDS", 30),
            max_attempts=as_int("SENESCYT_MAX_ATTEMPTS", 3),
            oficial_api_url=get("SENESCYT_OFICIAL_API_URL"),
            oficial_api_key=get("SENESCYT_OFICIAL_API_KEY"),
        ),
        scheduler=SchedulerSettings(
            enabled=as_bool("SCHEDULER_ENABLED", False),
            period_days=as_int("SCHEDULER_PERIOD_DAYS", 90),
            max_requests_per_hour=as_int("SCHEDULER_MAX_REQUESTS_PER_HOUR", 30),
            peak_start_hour=as_int("SCHEDULER_PEAK_START_HOUR", 8),
            peak_end_hour=as_int("SCHEDULER_PEAK_END_HOUR", 17),
            offpeak_end_hour=as_int("SCHEDULER_OFFPEAK_END_HOUR", 21),
            peak_weight=as_float("SCHEDULER_PEAK_WEIGHT", 1.0),
            offpeak_weight=as_float("SCHEDULER_OFFPEAK_WEIGHT", 0.35),
            min_delay_seconds=as_int("SCHEDULER_MIN_DELAY_SECONDS", 45),
            max_delay_seconds=as_int("SCHEDULER_MAX_DELAY_SECONDS", 240),
            backoff_base_seconds=as_int("SCHEDULER_BACKOFF_BASE_SECONDS", 300),
            backoff_max_seconds=as_int("SCHEDULER_BACKOFF_MAX_SECONDS", 7200),
            circuit_breaker_failures=as_int("SCHEDULER_CIRCUIT_BREAKER_FAILURES", 5),
        ),
        reports=ReportSettings(
            output_dir=Path(get("REPORTS_OUTPUT_DIR", "/app/storage/reports")),
            max_rows=as_int("REPORTS_MAX_ROWS", 100_000),
        ),
        security=SecuritySettings(
            password_min_length=as_int("PASSWORD_MIN_LENGTH", 10),
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Punto unico de acceso a la configuracion (cacheado por proceso)."""
    return _build_settings()
