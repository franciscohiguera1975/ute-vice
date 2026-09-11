"""Verifica la regla de dependencia de la arquitectura limpia.

Esta prueba es el guardian de la decision fundacional del proyecto: el dominio
no conoce a nadie. Sin ella, la regla se erosiona en semanas — basta un `import`
de conveniencia para atar las reglas de negocio a SQLAlchemy o a FastAPI, y a
partir de ahi ya no hay vuelta atras.

Si esta prueba falla, la solucion casi nunca es relajarla: es definir un puerto.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "src" / "app"

#: Lo que cada capa tiene permitido importar del propio proyecto.
REGLAS: dict[str, set[str]] = {
    # El dominio es autonomo: solo se conoce a si mismo.
    "domain": {"app.domain"},
    # La aplicacion orquesta el dominio. `app.core` se admite para configuracion
    # y registro; no arrastra dependencias de infraestructura.
    "application": {"app.domain", "app.application", "app.core"},
    # La infraestructura implementa los puertos del dominio.
    "infrastructure": {"app.domain", "app.application", "app.core", "app.infrastructure"},
}


def _modulos_de(capa: str) -> list[Path]:
    return sorted((RAIZ / capa).rglob("*.py"))


def _imports_internos(archivo: Path) -> set[str]:
    """Modulos de `app.*` que importa el archivo."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    encontrados: set[str] = set()

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            encontrados.update(alias.name for alias in nodo.names if alias.name.startswith("app."))
        elif (
            isinstance(nodo, ast.ImportFrom)
            and nodo.module
            and nodo.level == 0
            and nodo.module.startswith("app.")
        ):
            encontrados.add(nodo.module)
    return encontrados


def _prefijo_permitido(modulo: str, permitidos: set[str]) -> bool:
    return any(modulo == p or modulo.startswith(p + ".") for p in permitidos)


@pytest.mark.unit
@pytest.mark.parametrize("capa", sorted(REGLAS))
def test_la_capa_solo_importa_lo_permitido(capa: str) -> None:
    permitidos = REGLAS[capa]
    infracciones: list[str] = []

    for archivo in _modulos_de(capa):
        for modulo in _imports_internos(archivo):
            if not _prefijo_permitido(modulo, permitidos):
                relativo = archivo.relative_to(RAIZ.parent.parent)
                infracciones.append(f"{relativo} importa {modulo}")

    assert not infracciones, (
        f"La capa '{capa}' solo puede importar {sorted(permitidos)}.\n"
        "Infracciones:\n  - " + "\n  - ".join(infracciones) + "\n\n"
        "Si necesita algo de fuera, defina un puerto en app/domain/ports/ y "
        "haga que la infraestructura lo implemente."
    )


@pytest.mark.unit
def test_el_dominio_no_importa_librerias_de_infraestructura() -> None:
    """El dominio tampoco depende de librerias externas de E/S.

    Se prohiben explicitamente las que suelen colarse: el ORM, el framework web,
    el cliente HTTP y la libreria de validacion. Que el dominio use solo la
    biblioteca estandar es lo que lo hace probable en milisegundos.
    """
    prohibidas = {
        "sqlalchemy",
        "fastapi",
        "starlette",
        "pydantic",
        "httpx",
        "alembic",
        "jwt",
        "argon2",
        "openpyxl",
        "reportlab",
        "ldap3",
        "asyncpg",
    }
    infracciones: list[str] = []

    for archivo in _modulos_de("domain"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            nombres: list[str] = []
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                nombres = [nodo.module]

            for nombre in nombres:
                raiz = nombre.split(".")[0]
                if raiz in prohibidas:
                    infracciones.append(f"{archivo.name} importa {nombre}")

    assert not infracciones, (
        "El dominio debe depender solo de la biblioteca estandar.\n"
        "Infracciones:\n  - " + "\n  - ".join(infracciones)
    )


@pytest.mark.unit
def test_los_casos_de_uso_declaran_su_permiso() -> None:
    """Todo caso de uso de escritura debe declarar `permiso_requerido`.

    Un caso de uso sin permiso queda abierto a cualquiera que llegue al
    endpoint. Se admiten excepciones —el inicio de sesion, por ejemplo, es
    necesariamente publico— pero deben ser deliberadas y estar en esta lista.
    """
    import importlib
    import inspect
    import pkgutil

    from app.application.base import CasoDeUso

    # Operaciones publicas o autorizadas por otro medio (la sesion del propio
    # usuario), justificadas una a una.
    exentos = {
        "IniciarSesion",  # publico por definicion
        "IniciarSesionFederado",  # publico por definicion
        "RefrescarSesion",  # se autoriza con el token de refresco
        "CerrarSesion",  # idem
        "CerrarTodasLasSesiones",  # verifica la identidad en su cuerpo
        "CambiarContrasenaPropia",  # opera solo sobre la cuenta propia
        "ObtenerPerfil",  # opera solo sobre la cuenta propia
        "LimpiarTokensExpirados",  # tarea del sistema, sin actor
    }

    paquete = importlib.import_module("app.application.casos_uso")
    sin_permiso: list[str] = []

    for info in pkgutil.iter_modules(paquete.__path__):
        modulo = importlib.import_module(f"app.application.casos_uso.{info.name}")
        for nombre, clase in inspect.getmembers(modulo, inspect.isclass):
            if not issubclass(clase, CasoDeUso) or clase is CasoDeUso:
                continue
            if clase.__module__ != modulo.__name__:
                continue  # importado de otro modulo, ya se revisa alli
            if inspect.isabstract(clase):
                continue
            if clase.permiso_requerido is None and nombre not in exentos:
                sin_permiso.append(f"{info.name}.{nombre}")

    assert not sin_permiso, (
        "Estos casos de uso no declaran `permiso_requerido` y no estan en la "
        "lista de exentos:\n  - " + "\n  - ".join(sorted(sin_permiso))
    )
