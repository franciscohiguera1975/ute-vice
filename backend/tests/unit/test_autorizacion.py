"""Pruebas del control de acceso por roles.

La decision de diseno que se verifica aqui: la autorizacion se resuelve siempre
por **permiso**, nunca por rol. `Usuario.puede(permiso)` es el unico predicado
del sistema. Gracias a eso, agregar un rol nuevo no obliga a tocar ningun
endpoint ni ningun caso de uso.
"""

from __future__ import annotations

import pytest
from tests.conftest import hacer_usuario

from app.domain.entities.auth import Rol
from app.domain.enums import PERMISOS_POR_ROL, AuthProvider, Permiso, RolCodigo
from app.domain.errors import (
    ConflictoDeEstado,
    ReglaDeNegocioViolada,
    UsuarioBloqueado,
    UsuarioInactivo,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def catalogo() -> dict[RolCodigo, Rol]:
    return {
        codigo: Rol.desde_catalogo(codigo, permisos)
        for codigo, permisos in PERMISOS_POR_ROL.items()
    }


class TestPermisosPorRol:
    def test_admin_tiene_todos_los_permisos(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.ADMIN]})
        assert all(usuario.puede(p) for p in Permiso)

    def test_consulta_es_estrictamente_de_lectura(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.CONSULTA]})
        assert usuario.puede(Permiso.PERSONAS_LEER)
        assert usuario.puede(Permiso.TITULOS_LEER)
        assert usuario.puede(Permiso.DASHBOARD_VER)

        assert not usuario.puede(Permiso.PERSONAS_ESCRIBIR)
        assert not usuario.puede(Permiso.TITULOS_ESCRIBIR)
        assert not usuario.puede(Permiso.CONSULTAS_EJECUTAR)
        assert not usuario.puede(Permiso.REPORTES_GENERAR)
        assert not usuario.puede(Permiso.USUARIOS_LEER)

    def test_analista_opera_pero_no_administra(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.ANALISTA]})
        assert usuario.puede(Permiso.TITULOS_ESCRIBIR)
        assert usuario.puede(Permiso.CONSULTAS_RESOLVER)
        assert usuario.puede(Permiso.REPORTES_GENERAR)

        assert not usuario.puede(Permiso.CONSULTAS_ADMINISTRAR)
        assert not usuario.puede(Permiso.USUARIOS_ESCRIBIR)
        assert not usuario.puede(Permiso.ROLES_ADMINISTRAR)
        assert not usuario.puede(Permiso.PERSONAS_ESCRIBIR)

    def test_coordinador_administra_campanas_pero_no_usuarios(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.COORDINADOR]})
        assert usuario.puede(Permiso.CONSULTAS_ADMINISTRAR)
        assert usuario.puede(Permiso.PERSONAS_ESCRIBIR)
        assert usuario.puede(Permiso.USUARIOS_LEER)

        assert not usuario.puede(Permiso.USUARIOS_ESCRIBIR)
        assert not usuario.puede(Permiso.ROLES_ADMINISTRAR)

    def test_los_permisos_se_acumulan_entre_roles(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.CONSULTA], catalogo[RolCodigo.ANALISTA]})
        assert usuario.puede(Permiso.TITULOS_ESCRIBIR)  # del analista
        assert usuario.puede(Permiso.PERSONAS_LEER)  # de ambos

    def test_un_usuario_sin_roles_no_puede_nada(self) -> None:
        usuario = hacer_usuario(roles=set())
        assert not any(usuario.puede(p) for p in Permiso)

    def test_el_superusuario_pasa_por_encima_de_los_roles(self) -> None:
        usuario = hacer_usuario(roles=set(), superusuario=True)
        assert all(usuario.puede(p) for p in Permiso)


class TestPredicadosCompuestos:
    def test_puede_todo_exige_la_lista_completa(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.CONSULTA]})
        assert usuario.puede_todo(Permiso.PERSONAS_LEER, Permiso.TITULOS_LEER)
        assert not usuario.puede_todo(Permiso.PERSONAS_LEER, Permiso.PERSONAS_ESCRIBIR)

    def test_puede_alguno_basta_con_uno(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.CONSULTA]})
        assert usuario.puede_alguno(Permiso.PERSONAS_ESCRIBIR, Permiso.PERSONAS_LEER)
        assert not usuario.puede_alguno(Permiso.PERSONAS_ESCRIBIR, Permiso.USUARIOS_ESCRIBIR)


class TestProteccionesDelRol:
    def test_el_rol_admin_no_puede_quedarse_sin_permisos(self, catalogo) -> None:
        """Vaciar ADMIN dejaria el sistema sin forma de recuperar el control."""
        with pytest.raises(ReglaDeNegocioViolada, match="ADMIN"):
            catalogo[RolCodigo.ADMIN].reemplazar_permisos({Permiso.PERSONAS_LEER})

    def test_los_roles_del_sistema_no_se_eliminan(self, catalogo) -> None:
        with pytest.raises(ReglaDeNegocioViolada, match="sistema"):
            catalogo[RolCodigo.CONSULTA].asegurar_eliminable()

    def test_un_rol_propio_si_se_elimina(self) -> None:
        propio = Rol(codigo="AUDITOR", nombre="Auditor", es_sistema=False)
        propio.asegurar_eliminable()  # no lanza

    def test_otro_rol_del_sistema_si_admite_ajustar_permisos(self, catalogo) -> None:
        analista = catalogo[RolCodigo.ANALISTA]
        analista.reemplazar_permisos({Permiso.TITULOS_LEER})
        assert analista.permisos == {Permiso.TITULOS_LEER}


class TestEstadoDeLaCuenta:
    def test_una_cuenta_activa_puede_entrar(self) -> None:
        hacer_usuario().asegurar_puede_iniciar_sesion()  # no lanza

    def test_una_cuenta_desactivada_no_puede_entrar(self) -> None:
        with pytest.raises(UsuarioInactivo):
            hacer_usuario(activo=False).asegurar_puede_iniciar_sesion()

    def test_se_bloquea_al_acumular_intentos_fallidos(self) -> None:
        from datetime import UTC, datetime

        ahora = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
        usuario = hacer_usuario()

        for _ in range(4):
            usuario.registrar_intento_fallido(maximo=5, minutos_bloqueo=15, ahora=ahora)
        usuario.asegurar_puede_iniciar_sesion(ahora)  # aun no bloqueada

        usuario.registrar_intento_fallido(maximo=5, minutos_bloqueo=15, ahora=ahora)
        with pytest.raises(UsuarioBloqueado):
            usuario.asegurar_puede_iniciar_sesion(ahora)

    def test_el_bloqueo_expira_solo(self) -> None:
        from datetime import UTC, datetime, timedelta

        ahora = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
        usuario = hacer_usuario()
        for _ in range(5):
            usuario.registrar_intento_fallido(maximo=5, minutos_bloqueo=15, ahora=ahora)

        usuario.asegurar_puede_iniciar_sesion(ahora + timedelta(minutes=16))  # no lanza

    def test_un_acceso_correcto_limpia_los_intentos(self) -> None:
        from datetime import UTC, datetime

        ahora = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
        usuario = hacer_usuario()
        for _ in range(5):
            usuario.registrar_intento_fallido(maximo=5, minutos_bloqueo=15, ahora=ahora)

        usuario.registrar_acceso_exitoso(ahora)
        assert usuario.intentos_fallidos == 0
        assert usuario.bloqueado_hasta is None
        usuario.asegurar_puede_iniciar_sesion(ahora)

    def test_el_superusuario_no_puede_desactivarse(self) -> None:
        with pytest.raises(ReglaDeNegocioViolada, match="superusuario"):
            hacer_usuario(superusuario=True).desactivar()

    def test_un_usuario_debe_conservar_al_menos_un_rol(self, catalogo) -> None:
        usuario = hacer_usuario(roles={catalogo[RolCodigo.CONSULTA]})
        with pytest.raises(ReglaDeNegocioViolada, match="al menos un rol"):
            usuario.reemplazar_roles(set())


class TestCredencialesSegunProveedor:
    def test_una_cuenta_federada_no_admite_contrasena_local(self) -> None:
        """Darle credencial local a una cuenta de Google seria crear un vector
        de ataque que no existia."""
        usuario = hacer_usuario(proveedor=AuthProvider.GOOGLE, hash_contrasena=None)
        with pytest.raises(ConflictoDeEstado, match="GOOGLE"):
            usuario.establecer_hash("hash-nuevo")

    def test_una_cuenta_local_si_admite_contrasena(self) -> None:
        usuario = hacer_usuario()
        usuario.debe_cambiar_contrasena = True
        usuario.establecer_hash("hash-nuevo")
        assert usuario.hash_contrasena == "hash-nuevo"
        assert not usuario.debe_cambiar_contrasena

    def test_reconoce_si_usa_credencial_local(self) -> None:
        assert hacer_usuario().usa_credencial_local
        assert not hacer_usuario(hash_contrasena=None).usa_credencial_local
        assert not hacer_usuario(
            proveedor=AuthProvider.LDAP, hash_contrasena=None
        ).usa_credencial_local
