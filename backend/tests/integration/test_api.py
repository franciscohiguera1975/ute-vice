"""Pruebas de integracion de la API sobre PostgreSQL real.

Cubren lo que los dobles en memoria no pueden: el SQL que genera SQLAlchemy, las
restricciones del esquema, el comportamiento transaccional y la serializacion de
las respuestas HTTP.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

CEDULA = "1710034065"
OTRA_CEDULA = "0926687856"


class TestSalud:
    async def test_health_reporta_la_base_conectada(self, app_y_cliente) -> None:
        _, cliente = app_y_cliente
        respuesta = await cliente.get("/health")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == "ok"
        assert cuerpo["base_datos"] == "conectada"

    async def test_las_cabeceras_de_seguridad_estan_presentes(self, app_y_cliente) -> None:
        _, cliente = app_y_cliente
        respuesta = await cliente.get("/health")
        assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
        assert respuesta.headers["X-Frame-Options"] == "DENY"
        assert "X-Request-ID" in respuesta.headers

    async def test_el_identificador_de_peticion_se_respeta_si_llega(self, app_y_cliente) -> None:
        _, cliente = app_y_cliente
        respuesta = await cliente.get("/health", headers={"X-Request-ID": "traza-123"})
        assert respuesta.headers["X-Request-ID"] == "traza-123"


class TestAutenticacion:
    async def test_sin_token_devuelve_401(self, sembrado) -> None:
        _, cliente = sembrado
        respuesta = await cliente.get("/api/v1/personas")
        assert respuesta.status_code == 401
        assert respuesta.json()["codigo"] == "token_invalido"
        assert respuesta.headers.get("WWW-Authenticate") == "Bearer"

    async def test_con_token_invalido_devuelve_401(self, sembrado) -> None:
        _, cliente = sembrado
        respuesta = await cliente.get(
            "/api/v1/personas", headers={"Authorization": "Bearer basura"}
        )
        assert respuesta.status_code == 401

    async def test_el_error_tiene_siempre_la_misma_forma(self, sembrado) -> None:
        _, cliente = sembrado
        cuerpo = (await cliente.get("/api/v1/personas")).json()
        assert set(cuerpo) == {"codigo", "mensaje", "detalles", "request_id"}

    async def test_rotacion_del_token_de_refresco(self, sembrado) -> None:
        """Reutilizar un token ya canjeado se trata como robo: se cierran todas
        las sesiones del usuario."""
        from app.core.config import get_settings

        _, cliente = sembrado
        settings = get_settings()
        credenciales = {
            "email": settings.first_superuser_email,
            "contrasena": settings.first_superuser_password,
        }

        primera = (await cliente.post("/api/v1/auth/login", json=credenciales)).json()
        refresco = primera["tokens"]["refresco"]

        segunda = await cliente.post("/api/v1/auth/refrescar", json={"token_refresco": refresco})
        assert segunda.status_code == 200
        assert segunda.json()["tokens"]["refresco"] != refresco

        reutilizado = await cliente.post(
            "/api/v1/auth/refrescar", json={"token_refresco": refresco}
        )
        assert reutilizado.status_code == 401


class TestPersonas:
    async def test_ciclo_completo(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado

        creacion = await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={
                "cedula": CEDULA,
                "nombres": "ana maria",
                "apellidos": "yepez cordova",
                "unidad": "Vicerrectorado",
                "tipo_vinculacion": "ADMINISTRATIVO",
            },
        )
        assert creacion.status_code == 201, creacion.text
        persona = creacion.json()
        assert persona["nombre_completo"] == "Ana Maria Yepez Cordova"

        detalle = await cliente.get(f"/api/v1/personas/{persona['id']}", headers=cabeceras_admin)
        assert detalle.status_code == 200
        assert detalle.json()["total_titulos"] == 0

        modificacion = await cliente.patch(
            f"/api/v1/personas/{persona['id']}",
            headers=cabeceras_admin,
            json={"cargo": "Analista de sistemas"},
        )
        assert modificacion.status_code == 200
        assert modificacion.json()["cargo"] == "Analista de sistemas"

        borrado = await cliente.delete(f"/api/v1/personas/{persona['id']}", headers=cabeceras_admin)
        assert borrado.status_code == 200

    async def test_la_unicidad_de_cedula_la_respalda_la_base(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        datos = {"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"}
        assert (
            await cliente.post("/api/v1/personas", headers=cabeceras_admin, json=datos)
        ).status_code == 201
        repetida = await cliente.post("/api/v1/personas", headers=cabeceras_admin, json=datos)
        assert repetida.status_code == 409

    async def test_la_cedula_invalida_se_rechaza_en_el_borde(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={"cedula": "1234567890", "nombres": "Mala", "apellidos": "Cedula"},
        )
        assert respuesta.status_code == 422

    async def test_la_busqueda_ignora_acentos(self, sembrado, cabeceras_admin) -> None:
        """La clave de busqueda esta normalizada: buscar 'munoz' encuentra
        'Muñoz'."""
        _, cliente = sembrado
        await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={"cedula": CEDULA, "nombres": "José", "apellidos": "Muñoz Peña"},
        )
        respuesta = await cliente.get("/api/v1/personas?texto=munoz", headers=cabeceras_admin)
        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 1

    async def test_importacion_parcial(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/personas/importar",
            headers=cabeceras_admin,
            json=[
                {"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
                {"cedula": "1234567890", "nombres": "Mala", "apellidos": "Cedula"},
                {"cedula": OTRA_CEDULA, "nombres": "Luis", "apellidos": "Munoz"},
            ],
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["creadas"] == 2
        assert len(cuerpo["rechazadas"]) == 1
        assert not cuerpo["exitosa"]


class TestConsultas:
    async def test_consulta_puntual_y_su_rastro(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        persona = (
            await cliente.post(
                "/api/v1/personas",
                headers=cabeceras_admin,
                json={"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
            )
        ).json()

        consulta = await cliente.post(
            f"/api/v1/consultas/personas/{persona['id']}", headers=cabeceras_admin
        )
        assert consulta.status_code == 200, consulta.text
        registro = consulta.json()["log"]
        assert registro["estado"] in {"EXITO", "SIN_DATOS"}

        historico = await cliente.get("/api/v1/consultas/logs", headers=cabeceras_admin)
        assert historico.json()["total"] == 1

        detalle = await cliente.get(f"/api/v1/personas/{persona['id']}", headers=cabeceras_admin)
        assert detalle.json()["total_titulos"] == registro["titulos_encontrados"]

    async def test_la_regla_de_cobertura_se_aplica(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        persona = (
            await cliente.post(
                "/api/v1/personas",
                headers=cabeceras_admin,
                json={"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
            )
        ).json()

        await cliente.post(f"/api/v1/consultas/personas/{persona['id']}", headers=cabeceras_admin)
        repetida = await cliente.post(
            f"/api/v1/consultas/personas/{persona['id']}", headers=cabeceras_admin
        )
        assert repetida.status_code == 409

        forzada = await cliente.post(
            f"/api/v1/consultas/personas/{persona['id']}?forzar=true",
            headers=cabeceras_admin,
        )
        assert forzada.status_code == 200
        assert forzada.json()["log"]["titulos_nuevos"] == 0

    async def test_ciclo_de_un_job_de_cobertura(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        for cedula in (CEDULA, OTRA_CEDULA):
            await cliente.post(
                "/api/v1/personas",
                headers=cabeceras_admin,
                json={"cedula": cedula, "nombres": "Persona", "apellidos": "Prueba"},
            )

        creacion = await cliente.post(
            "/api/v1/consultas/jobs",
            headers=cabeceras_admin,
            json={"nombre": "Campana de prueba", "iniciar_inmediatamente": True},
        )
        assert creacion.status_code == 201, creacion.text
        job = creacion.json()
        assert job["job"]["total_items"] == 2
        job_id = job["job"]["id"]

        segundo = await cliente.post(
            "/api/v1/consultas/jobs",
            headers=cabeceras_admin,
            json={"nombre": "Otra campana"},
        )
        assert segundo.status_code == 409

        for _ in range(6):
            paso = await cliente.post(
                f"/api/v1/consultas/jobs/{job_id}/avanzar", headers=cabeceras_admin
            )
            assert paso.status_code == 200
            if paso.json()["job_completado"]:
                break

        estado = await cliente.get(f"/api/v1/consultas/jobs/{job_id}", headers=cabeceras_admin)
        assert estado.json()["procesados" if False else "completados"] >= 1

    async def test_control_del_job(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
        )
        job_id = (
            await cliente.post(
                "/api/v1/consultas/jobs",
                headers=cabeceras_admin,
                json={"nombre": "Campana", "iniciar_inmediatamente": True},
            )
        ).json()["job"]["id"]

        pausa = await cliente.post(
            f"/api/v1/consultas/jobs/{job_id}/control",
            headers=cabeceras_admin,
            json={"accion": "pausar", "motivo": "revision"},
        )
        assert pausa.json()["estado"] == "PAUSADO"

        avance = await cliente.post(
            f"/api/v1/consultas/jobs/{job_id}/avanzar", headers=cabeceras_admin
        )
        assert not avance.json()["hubo_consulta"]

        reanudacion = await cliente.post(
            f"/api/v1/consultas/jobs/{job_id}/control",
            headers=cabeceras_admin,
            json={"accion": "reanudar"},
        )
        assert reanudacion.json()["estado"] == "EN_CURSO"


class TestReportes:
    @pytest.mark.parametrize(
        ("formato", "firma"),
        [("XLSX", b"PK"), ("CSV", b"\xef\xbb\xbf"), ("PDF", b"%PDF")],
    )
    async def test_genera_los_tres_formatos(
        self, sembrado, cabeceras_admin, formato: str, firma: bytes
    ) -> None:
        _, cliente = sembrado
        await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
        )
        respuesta = await cliente.get(
            f"/api/v1/reportes/personas?formato={formato}", headers=cabeceras_admin
        )
        assert respuesta.status_code == 200
        assert respuesta.content.startswith(firma)
        assert "attachment" in respuesta.headers["content-disposition"]


class TestTablero:
    async def test_devuelve_los_indicadores(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await cliente.post(
            "/api/v1/personas",
            headers=cabeceras_admin,
            json={"cedula": CEDULA, "nombres": "Ana", "apellidos": "Yepez"},
        )
        respuesta = await cliente.get("/api/v1/tablero", headers=cabeceras_admin)
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["cobertura"]["total_personas"] == 1
        assert cuerpo["cobertura"]["nunca_consultadas"] == 1
        assert "por_nivel" in cuerpo["titulos"]


class TestControlDeAcceso:
    """Verifica el RBAC sobre la API real, no solo en el dominio."""

    @pytest.fixture
    async def cabeceras_lector(self, sembrado, cabeceras_admin):  # type: ignore[no-untyped-def]
        _, cliente = sembrado
        creacion = await cliente.post(
            "/api/v1/usuarios",
            headers=cabeceras_admin,
            json={
                "email": "lector@ute.edu.ec",
                "nombre_completo": "Usuario Lector",
                "contrasena": "Lectura#2026.Ok",
                "roles": ["CONSULTA"],
            },
        )
        assert creacion.status_code == 201, creacion.text
        acceso = await cliente.post(
            "/api/v1/auth/login",
            json={"email": "lector@ute.edu.ec", "contrasena": "Lectura#2026.Ok"},
        )
        return {"Authorization": f"Bearer {acceso.json()['tokens']['acceso']}"}

    async def test_el_rol_consulta_puede_leer(self, sembrado, cabeceras_lector) -> None:
        _, cliente = sembrado
        assert (await cliente.get("/api/v1/personas", headers=cabeceras_lector)).status_code == 200

    @pytest.mark.parametrize(
        ("metodo", "ruta"),
        [
            ("post", "/api/v1/personas"),
            ("get", "/api/v1/usuarios"),
            ("get", "/api/v1/reportes/titulos"),
            ("post", "/api/v1/consultas/jobs"),
        ],
    )
    async def test_el_rol_consulta_no_puede_escribir_ni_administrar(
        self, sembrado, cabeceras_lector, metodo: str, ruta: str
    ) -> None:
        _, cliente = sembrado
        peticion = getattr(cliente, metodo)
        respuesta = (
            await peticion(ruta, headers=cabeceras_lector, json={})
            if metodo == "post"
            else await peticion(ruta, headers=cabeceras_lector)
        )
        assert respuesta.status_code == 403, f"{metodo.upper()} {ruta} -> {respuesta.status_code}"
