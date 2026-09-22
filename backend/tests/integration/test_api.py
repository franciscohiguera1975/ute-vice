"""Pruebas de integracion de la API sobre PostgreSQL real.

Cubren lo que los dobles en memoria no pueden: el SQL que genera SQLAlchemy, las
restricciones del esquema, el comportamiento transaccional y la serializacion de
las respuestas HTTP.
"""

from __future__ import annotations

from typing import ClassVar

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


class TestTableroDelDistributivo:
    """El tablero del distributivo, sobre datos cargados por la propia API.

    Se carga un PAO por el endpoint de importacion y se leen sus indicadores:
    asi la prueba cubre el camino entero —archivo, catalogos, periodos y
    agregaciones— y no solo el SQL de las agregaciones.
    """

    @staticmethod
    def _archivo(estado: str = "OK", identificacion: str = CEDULA) -> bytes:
        """Un PAO minimo en memoria, con las columnas que exige el lector."""
        from io import BytesIO

        from openpyxl import Workbook

        cabecera = [
            "Identificación",
            "Apellidos y Nombres",
            "Sede",
            "Nivel",
            "Facultad",
            "Carrera/Programa",
            "Modalidad",
            "Da",
            "Ga",
            "Titularidad",
            "Categoría",
            "Dedicación",
            "Relación Laboral",
            "Estado de la Validación",
            "N.º Semanas",
            "Fase",
            "Tutores Posgrado",
            "Tutores Medicina",
        ]
        fila = [
            identificacion,
            "YEPEZ ANA",
            "SEDE QUITO",
            "GRADO",
            "ARQUITECTURA Y URBANISMO",
            "ARQUITECTURA",
            "PRESENCIAL",
            20,
            4,
            "NO TITULAR",
            "AUXILIAR",
            "TIEMPO COMPLETO",
            "Dependencia Laboral",
            estado,
            16,
            "Planificación",
            "No",
            "No",
        ]

        libro = Workbook()
        hoja = libro.active
        hoja.append(cabecera)
        hoja.append(fila)
        memoria = BytesIO()
        libro.save(memoria)
        return memoria.getvalue()

    async def _cargar(self, cliente, cabeceras, semestre: str, **campos):  # type: ignore[no-untyped-def]
        return await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras,
            files={"archivo": (f"PAO_{semestre}.xlsx", self._archivo(**campos))},
            data={"semestre": semestre, "actualizar_existentes": "true"},
        )

    async def test_carga_un_pao_y_calcula_sus_indicadores(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado

        carga = await self._cargar(cliente, cabeceras_admin, "2026-2")
        assert carga.status_code == 200, carga.text
        assert carga.json()["filas_creadas"] == 1
        assert carga.json()["periodo"] == "2026-2"

        respuesta = await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()

        # Un archivo de grado produce el periodo `262651`: `26` anio, `2`
        # semestre, `65` grado, `1` ordinario. El tablero compara grupos, asi
        # que llega como lista aunque el grupo tenga un solo periodo.
        assert cuerpo["actual"]["codigos"] == ["262651"]
        assert cuerpo["actual"]["total"] == 1
        assert cuerpo["actual"]["aprobadas"] == 1
        assert cuerpo["actual"]["porcentaje_aprobado"] == 100.0
        assert cuerpo["anterior"] is None
        assert cuerpo["por_facultad"][0]["total_actual"] == 1

    async def test_compara_con_el_periodo_anterior(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado

        assert (
            await self._cargar(cliente, cabeceras_admin, "2026-1", estado="Validación Pendiente")
        ).status_code == 200
        assert (await self._cargar(cliente, cabeceras_admin, "2026-2")).status_code == 200

        cuerpo = (await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)).json()

        assert cuerpo["actual"]["codigos"] == ["262651"]
        assert cuerpo["anterior"]["codigos"] == ["261651"]
        assert cuerpo["actual"]["porcentaje_aprobado"] == 100.0
        assert cuerpo["anterior"]["porcentaje_aprobado"] == 0.0
        assert cuerpo["por_facultad"][0]["variacion"] == 100.0

    async def test_recargar_el_mismo_periodo_actualiza_en_vez_de_duplicar(
        self, sembrado, cabeceras_admin
    ) -> None:
        """Es el caso habitual: el PAO llega corregido y se vuelve a subir."""
        _, cliente = sembrado

        primera = await self._cargar(
            cliente, cabeceras_admin, "2026-2", estado="Validación Pendiente"
        )
        assert primera.json()["filas_creadas"] == 1

        segunda = await self._cargar(cliente, cabeceras_admin, "2026-2", estado="OK")
        assert segunda.json()["filas_creadas"] == 0
        assert segunda.json()["filas_actualizadas"] == 1

        cuerpo = (await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)).json()
        assert cuerpo["actual"]["total"] == 1
        assert cuerpo["actual"]["aprobadas"] == 1

    async def test_rechaza_un_archivo_que_no_es_una_hoja_de_calculo(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("pao.xlsx", b"esto no es un libro")},
            data={"semestre": "2026-2"},
        )
        assert respuesta.status_code == 422

    async def test_rechaza_una_extension_que_no_corresponde(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("pao.csv", self._archivo())},
            data={"semestre": "2026-2"},
        )
        assert respuesta.status_code == 422

    async def test_sin_carga_el_tablero_responde_vacio_y_no_falla(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        cuerpo = (await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)).json()

        assert cuerpo["periodos"] == []
        assert cuerpo["actual"] is None


class TestAccesoAlTableroDelDistributivo:
    """Quien ve el tablero y quien puede cargar un PAO.

    El rol de consulta del distributivo es de solo lectura: se creo para dos
    usuarios que consultan y exportan, y **no** tiene `dashboard:ver`. El
    tablero del distributivo pide `distributivo:leer` justamente para que ese
    rol lo vea sin abrirle el tablero general ni la carga de archivos.
    """

    @pytest.fixture
    async def cabeceras_consulta(self, sembrado, cabeceras_admin):  # type: ignore[no-untyped-def]
        _, cliente = sembrado
        creacion = await cliente.post(
            "/api/v1/usuarios",
            headers=cabeceras_admin,
            json={
                "email": "consulta.distributivo@ute.edu.ec",
                "nombre_completo": "Consulta Distributivo",
                "contrasena": "Consulta#2026.Ok",
                "roles": ["CONSULTA_DISTRIBUTIVO"],
            },
        )
        assert creacion.status_code == 201, creacion.text
        acceso = await cliente.post(
            "/api/v1/auth/login",
            json={
                "email": "consulta.distributivo@ute.edu.ec",
                "contrasena": "Consulta#2026.Ok",
            },
        )
        return {"Authorization": f"Bearer {acceso.json()['tokens']['acceso']}"}

    async def test_el_rol_de_consulta_ve_el_tablero(self, sembrado, cabeceras_consulta) -> None:
        _, cliente = sembrado
        respuesta = await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_consulta)
        assert respuesta.status_code == 200

    async def test_el_rol_de_consulta_no_ve_el_tablero_general(
        self, sembrado, cabeceras_consulta
    ) -> None:
        _, cliente = sembrado
        assert (await cliente.get("/api/v1/tablero", headers=cabeceras_consulta)).status_code == 403

    async def test_el_rol_de_consulta_no_puede_cargar_un_pao(
        self, sembrado, cabeceras_consulta
    ) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_consulta,
            files={"archivo": ("pao.xlsx", TestTableroDelDistributivo._archivo())},
            data={"semestre": "2026-2"},
        )
        assert respuesta.status_code == 403

    async def test_sin_token_no_se_puede_cargar(self, sembrado) -> None:
        _, cliente = sembrado
        respuesta = await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            files={"archivo": ("pao.xlsx", TestTableroDelDistributivo._archivo())},
            data={"semestre": "2026-2"},
        )
        assert respuesta.status_code == 401


class TestResumenesDelDistributivo:
    """Comparacion de dos grupos de periodos.

    Lo que se protege es que se comparen **grupos** y no periodos sueltos: un
    semestre son tres periodos —tecnologia, grado y posgrado—, y comparar solo
    el de grado dejaria fuera media institucion.
    """

    async def _cargar(self, cliente, cabeceras, semestre, **campos):  # type: ignore[no-untyped-def]
        return await TestTableroDelDistributivo()._cargar(cliente, cabeceras, semestre, **campos)

    async def test_sin_grupos_compara_los_dos_ultimos_semestres(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-1", estado="Validación Pendiente")
        await self._cargar(cliente, cabeceras_admin, "2026-2")

        respuesta = await cliente.get("/api/v1/distributivo/resumenes", headers=cabeceras_admin)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()

        assert cuerpo["grupo_a"]["codigos"] == ["261651"]
        assert cuerpo["grupo_b"]["codigos"] == ["262651"]
        assert cuerpo["avance"][0]["codigo"] == "FAU"
        assert cuerpo["avance"][0]["docentes_a"] == 1
        assert cuerpo["avance"][0]["docentes_b"] == 1
        assert cuerpo["avance"][0]["filas_aprobadas_b"] == 1
        assert cuerpo["avance"][0]["porcentaje_aprobado_b"] == 100.0

    async def test_un_grupo_reune_los_periodos_de_todo_un_semestre(
        self, sembrado, cabeceras_admin
    ) -> None:
        """El mismo semestre con dos facultades produce dos periodos distintos.

        `ARQUITECTURA Y URBANISMO` va a grado y `UNIDAD ACADEMICA … TECNICA Y
        TECNOLOGICA` a tecnologia: `261651` y `261151`. El grupo tiene que
        traer los dos.
        """
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-1")
        await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={
                "archivo": (
                    "tec.xlsx",
                    _pao_de_tecnologia(identificacion=OTRA_CEDULA),
                )
            },
            data={"semestre": "2026-1", "actualizar_existentes": "true"},
        )

        cuerpo = (
            await cliente.get("/api/v1/distributivo/resumenes", headers=cabeceras_admin)
        ).json()

        # Un solo semestre cargado: es el actual —grupo 2—, sin referencia.
        assert sorted(cuerpo["grupo_b"]["codigos"]) == ["261151", "261651"]
        assert cuerpo["grupo_b"]["docentes"] == 2
        assert {f["codigo"] for f in cuerpo["avance"]} == {"FAU", "UAEFTT"}

    async def test_los_docentes_distintos_no_son_la_suma_por_facultad(
        self, sembrado, cabeceras_admin
    ) -> None:
        """Un docente en dos facultades cuenta una vez en el total y dos en la columna.

        Es la diferencia que hace que las dos filas de total de la pantalla no
        coincidan, y hay que poder explicarla.
        """
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-1")
        await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("tec.xlsx", _pao_de_tecnologia(identificacion=CEDULA))},
            data={"semestre": "2026-1", "actualizar_existentes": "true"},
        )

        cuerpo = (
            await cliente.get("/api/v1/distributivo/resumenes", headers=cabeceras_admin)
        ).json()

        assert cuerpo["grupo_b"]["docentes"] == 1
        assert sum(f["docentes_b"] for f in cuerpo["avance"]) == 2

    async def test_desglosa_todos_los_estados_por_facultad(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-2", estado="Error")

        cuerpo = (
            await cliente.get("/api/v1/distributivo/resumenes", headers=cabeceras_admin)
        ).json()

        # Con un solo semestre cargado, el grupo B queda vacio y todo cae en A.
        estados = cuerpo["estados_a"] or cuerpo["estados_b"]
        assert estados[0]["con_error"] == 1
        assert estados[0]["ok"] == 0
        assert estados[0]["total"] == 1
        # Una fila con error esta evaluada: el porcentaje aprobado es 0, no «—».
        assert estados[0]["evaluadas"] == 1
        assert estados[0]["porcentaje_aprobado"] == 0.0

    async def test_acepta_los_grupos_que_se_le_indiquen(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2025-2")
        await self._cargar(cliente, cabeceras_admin, "2026-2")

        periodos = (
            await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)
        ).json()["periodos"]
        por_codigo = {p["codigo"]: p["id"] for p in periodos}

        cuerpo = (
            await cliente.get(
                "/api/v1/distributivo/resumenes",
                headers=cabeceras_admin,
                params={"grupo_a": por_codigo["252651"], "grupo_b": por_codigo["262651"]},
            )
        ).json()

        assert cuerpo["grupo_a"]["codigos"] == ["252651"]
        assert cuerpo["grupo_b"]["codigos"] == ["262651"]

    async def test_el_rol_de_consulta_ve_los_resumenes(self, sembrado, cabeceras_admin) -> None:
        """Son de solo lectura: el rol estrecho tiene que poder abrirlos."""
        _, cliente = sembrado
        await cliente.post(
            "/api/v1/usuarios",
            headers=cabeceras_admin,
            json={
                "email": "solo.lectura@ute.edu.ec",
                "nombre_completo": "Solo Lectura",
                "contrasena": "Lectura#2026.Ok",
                "roles": ["CONSULTA_DISTRIBUTIVO"],
            },
        )
        acceso = await cliente.post(
            "/api/v1/auth/login",
            json={"email": "solo.lectura@ute.edu.ec", "contrasena": "Lectura#2026.Ok"},
        )
        cabeceras = {"Authorization": f"Bearer {acceso.json()['tokens']['acceso']}"}

        respuesta = await cliente.get("/api/v1/distributivo/resumenes", headers=cabeceras)
        assert respuesta.status_code == 200


class TestHorasPorDocentes:
    """Horas de `Da` por carrera y facultad, acotadas a una dedicacion o a todas."""

    _CABECERA: ClassVar[list[str]] = [
        "Identificación",
        "Apellidos y Nombres",
        "Sede",
        "Nivel",
        "Facultad",
        "Carrera/Programa",
        "Modalidad",
        "Da",
        "Ga",
        "Titularidad",
        "Categoría",
        "Dedicación",
        "Relación Laboral",
        "Estado de la Validación",
        "N.º Semanas",
        "Fase",
        "Tutores Posgrado",
        "Tutores Medicina",
    ]

    @classmethod
    def _fila(cls, identificacion: str, facultad: str, carrera: str, dedicacion: str) -> list:
        return [
            identificacion,
            "APELLIDO NOMBRE",
            "SEDE QUITO",
            "GRADO",
            facultad,
            carrera,
            "PRESENCIAL",
            20,
            4,
            "NO TITULAR",
            "AUXILIAR",
            dedicacion,
            "Dependencia Laboral",
            "OK",
            16,
            "Planificación",
            "No",
            "No",
        ]

    @classmethod
    def _archivo(cls, *filas: list) -> bytes:
        from io import BytesIO

        from openpyxl import Workbook

        libro = Workbook()
        hoja = libro.active
        hoja.append(cls._CABECERA)
        for f in filas:
            hoja.append(f)
        memoria = BytesIO()
        libro.save(memoria)
        return memoria.getvalue()

    async def _cargar(self, cliente, cabeceras, semestre: str, *filas: list):
        return await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras,
            files={"archivo": (f"PAO_{semestre}.xlsx", self._archivo(*filas))},
            data={"semestre": semestre, "actualizar_existentes": "true"},
        )

    async def test_sin_dedicacion_incluye_a_todos(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(
            cliente,
            cabeceras_admin,
            "2026-2",
            self._fila("1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"),
            self._fila("0926687856", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO COMPLETO"),
        )

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes", headers=cabeceras_admin
        )
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()

        assert cuerpo["docentes"] == 2
        assert cuerpo["horas_da"] == 40.0
        assert cuerpo["por_facultad"][0]["docentes"] == 2

    async def test_filtra_por_la_dedicacion_elegida(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(
            cliente,
            cabeceras_admin,
            "2026-2",
            self._fila("1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"),
            self._fila("0926687856", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO COMPLETO"),
            self._fila(
                "1102223335", "CIENCIAS DE LA SALUD EUGENIO ESPEJO", "MEDICINA", "TIEMPO PARCIAL"
            ),
        )

        catalogo = (
            await cliente.get("/api/v1/catalogos/dedicaciones/opciones", headers=cabeceras_admin)
        ).json()
        tiempo_parcial = next(o for o in catalogo if o["nombre"].upper() == "TIEMPO PARCIAL")

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes",
            headers=cabeceras_admin,
            params={"dedicacion_id": tiempo_parcial["id"]},
        )
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()

        assert cuerpo["docentes"] == 2
        assert cuerpo["horas_da"] == 40.0
        assert {f["codigo"] for f in cuerpo["por_facultad"]} == {"FAU", "FCSEE"}
        assert {c["carrera"] for c in cuerpo["por_carrera"]} == {
            "UIO:ARQUITECTURA - GRADO - PRESENCIAL",
            "UIO:MEDICINA - GRADO - PRESENCIAL",
        }

    async def test_una_carrera_en_dos_facultades_no_se_confunde(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        await self._cargar(
            cliente,
            cabeceras_admin,
            "2026-2",
            self._fila("1710034065", "ARQUITECTURA Y URBANISMO", "DISEÑO", "TIEMPO PARCIAL"),
            self._fila(
                "0926687856",
                "CIENCIAS DE LA SALUD EUGENIO ESPEJO",
                "DISEÑO",
                "TIEMPO PARCIAL",
            ),
        )

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes", headers=cabeceras_admin
        )
        cuerpo = respuesta.json()

        assert len(cuerpo["por_carrera"]) == 2
        facultades = {c["facultad_codigo"] for c in cuerpo["por_carrera"]}
        assert facultades == {"FAU", "FCSEE"}

    async def test_sin_umbral_no_calcula_bajo_horas(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(
            cliente,
            cabeceras_admin,
            "2026-2",
            self._fila("1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"),
        )

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes", headers=cabeceras_admin
        )
        assert respuesta.json()["bajo_horas"] == []

    async def test_lista_los_docentes_bajo_el_umbral(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        # `_fila` carga 20 horas de Da; se sube una segunda con menos para
        # poder distinguir quien queda bajo el umbral y quien no.
        await self._cargar(
            cliente,
            cabeceras_admin,
            "2026-2",
            self._fila("1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"),
        )
        pocas_horas = self._fila(
            "0926687856", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"
        )
        pocas_horas[self._CABECERA.index("Da")] = 3
        await self._cargar(cliente, cabeceras_admin, "2026-2", pocas_horas)

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes",
            headers=cabeceras_admin,
            params={"menos_de": 5},
        )
        assert respuesta.status_code == 200, respuesta.text
        bajo_horas = respuesta.json()["bajo_horas"]

        assert len(bajo_horas) == 1
        assert bajo_horas[0]["identificacion"] == "0926687856"
        assert bajo_horas[0]["horas_da"] == 3.0
        assert bajo_horas[0]["carrera"] == "UIO:ARQUITECTURA - GRADO - PRESENCIAL"

    async def test_excluir_sin_horas_deja_fuera_a_quien_tiene_cero(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        pocas_horas = self._fila(
            "1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"
        )
        pocas_horas[self._CABECERA.index("Da")] = 3
        sin_horas = self._fila(
            "0926687856", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"
        )
        sin_horas[self._CABECERA.index("Da")] = 0
        await self._cargar(cliente, cabeceras_admin, "2026-2", pocas_horas, sin_horas)

        con_ceros = (
            await cliente.get(
                "/api/v1/distributivo/horas-por-docentes",
                headers=cabeceras_admin,
                params={"menos_de": 5},
            )
        ).json()["bajo_horas"]
        assert {d["identificacion"] for d in con_ceros} == {"1710034065", "0926687856"}

        sin_ceros = (
            await cliente.get(
                "/api/v1/distributivo/horas-por-docentes",
                headers=cabeceras_admin,
                params={"menos_de": 5, "excluir_sin_horas": "true"},
            )
        ).json()["bajo_horas"]
        assert {d["identificacion"] for d in sin_ceros} == {"1710034065"}


class TestExportarHorasPorDocentes:
    """Descarga de las tres tablas de horas por docentes.

    Salen del mismo caso de uso que la pantalla: el archivo no puede decir
    otra cosa que lo que se esta viendo.
    """

    async def _preparar(self, cliente, cabeceras) -> None:  # type: ignore[no-untyped-def]
        await TestHorasPorDocentes()._cargar(
            cliente,
            cabeceras,
            "2026-2",
            TestHorasPorDocentes._fila(
                "1710034065", "ARQUITECTURA Y URBANISMO", "ARQUITECTURA", "TIEMPO PARCIAL"
            ),
        )

    @pytest.mark.parametrize("resumen", ["facultad", "carrera"])
    async def test_exporta_facultad_y_carrera(
        self, sembrado, cabeceras_admin, resumen: str
    ) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            f"/api/v1/distributivo/horas-por-docentes/exportar?resumen={resumen}&formato=XLSX",
            headers=cabeceras_admin,
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.content.startswith(b"PK")
        assert "attachment" in respuesta.headers["content-disposition"]

    async def test_exporta_bajo_horas_con_umbral(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes/exportar",
            headers=cabeceras_admin,
            params={"resumen": "bajo_horas", "menos_de": 50, "formato": "CSV"},
        )

        assert respuesta.status_code == 200, respuesta.text
        texto = respuesta.content.decode("utf-8-sig")
        assert "1710034065" in texto

    async def test_bajo_horas_sin_umbral_se_rechaza(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/horas-por-docentes/exportar?resumen=bajo_horas",
            headers=cabeceras_admin,
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["detalles"]["campo"] == "menos_de"


def _pao_de_tecnologia(*, identificacion: str) -> bytes:
    """Un PAO de la unidad tecnologica, que va a un periodo distinto."""
    from io import BytesIO

    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.append(["Identificación", "Sede", "Nivel", "Facultad", "Carrera/Programa", "Da"])
    hoja.append(
        [
            identificacion,
            "SEDE QUITO",
            "GRADO",
            "UNIDAD ACADÉMICA ESPECIALIZADA EN LA FORMACIÓN TÉCNICA Y TECNOLÓGICA",
            "DESARROLLO DE SOFTWARE",
            12,
        ]
    )
    memoria = BytesIO()
    libro.save(memoria)
    return memoria.getvalue()


class TestExportarResumenes:
    """Descarga de los resumenes en los tres formatos.

    Salen del mismo caso de uso que la pantalla: el archivo no puede decir otra
    cosa que lo que se esta viendo.
    """

    async def _preparar(self, cliente, cabeceras) -> None:  # type: ignore[no-untyped-def]
        carga = TestTableroDelDistributivo()
        await carga._cargar(cliente, cabeceras, "2026-1", estado="Validación Pendiente")
        await carga._cargar(cliente, cabeceras, "2026-2")

    @pytest.mark.parametrize(
        ("formato", "firma"),
        [("XLSX", b"PK"), ("CSV", b"\xef\xbb\xbf"), ("PDF", b"%PDF")],
    )
    async def test_los_tres_formatos(
        self, sembrado, cabeceras_admin, formato: str, firma: bytes
    ) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            f"/api/v1/distributivo/resumenes/exportar?formato={formato}",
            headers=cabeceras_admin,
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.content.startswith(firma)
        assert "attachment" in respuesta.headers["content-disposition"]

    async def test_el_resumen_de_estados_elige_el_grupo(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar?resumen=estados&grupo=a&formato=CSV",
            headers=cabeceras_admin,
        )

        assert respuesta.status_code == 200
        texto = respuesta.content.decode("utf-8-sig")
        assert "Estados del distributivo por facultad" in texto
        # El grupo A es 2026-1, cuya unica fila quedo pendiente de validar.
        assert "261651" in texto

    async def test_el_excel_lleva_cabecera_de_color_y_bandas_pastel(
        self, sembrado, cabeceras_admin
    ) -> None:
        """La presentacion es parte del entregable: se revisa, no se supone."""
        from io import BytesIO

        from openpyxl import load_workbook

        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar?formato=XLSX", headers=cabeceras_admin
        )
        hoja = load_workbook(BytesIO(respuesta.content)).active
        assert hoja is not None

        # La cabecera de la tabla es la primera fila cuya celda A tiene relleno
        # propio; antes van el titulo, el subtitulo y la constancia de filtros.
        cabecera = next(
            fila for fila in range(1, 15) if hoja.cell(row=fila, column=1).value == "Facultad"
        )

        colores = {
            hoja.cell(row=cabecera, column=col).fill.fgColor.rgb
            for col in range(1, hoja.max_column + 1)
        }
        # Varios bloques de color, no una cabecera de un solo tono.
        assert len({c for c in colores if c}) >= 3

        primera, segunda = cabecera + 1, cabecera + 2
        if hoja.cell(row=segunda, column=1).value is not None:
            banda = hoja.cell(row=segunda, column=1).fill.fgColor.rgb
            sin_banda = hoja.cell(row=primera, column=1).fill.fgColor.rgb
            assert banda != sin_banda
            assert str(banda).endswith("EAF3FA")

    async def test_el_rol_de_consulta_puede_descargarlos(self, sembrado, cabeceras_admin) -> None:
        """Tiene `reportes:generar` justamente para esto."""
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)
        await cliente.post(
            "/api/v1/usuarios",
            headers=cabeceras_admin,
            json={
                "email": "descarga@ute.edu.ec",
                "nombre_completo": "Descarga Resumenes",
                "contrasena": "Lectura#2026.Ok",
                "roles": ["CONSULTA_DISTRIBUTIVO"],
            },
        )
        acceso = await cliente.post(
            "/api/v1/auth/login",
            json={"email": "descarga@ute.edu.ec", "contrasena": "Lectura#2026.Ok"},
        )
        cabeceras = {"Authorization": f"Bearer {acceso.json()['tokens']['acceso']}"}

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar?formato=XLSX", headers=cabeceras
        )
        assert respuesta.status_code == 200

    async def test_sin_datos_no_se_genera_un_archivo_vacio(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar", headers=cabeceras_admin
        )
        assert respuesta.status_code == 422


class TestAmbitoDelReporte:
    """El selector encadenado de la pantalla de exportacion.

    Elegido el periodo se acotan las facultades; elegida la facultad se acotan
    las carreras. Ninguna de las dos relaciones vive en una columna del
    catalogo: se derivan de las filas, que es lo unico que no miente.
    """

    async def _cargar(self, cliente, cabeceras, semestre, **campos):  # type: ignore[no-untyped-def]
        return await TestTableroDelDistributivo()._cargar(cliente, cabeceras, semestre, **campos)

    async def _periodos(self, cliente, cabeceras):  # type: ignore[no-untyped-def]
        cuerpo = (await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras)).json()
        return {p["codigo"]: p["id"] for p in cuerpo["periodos"]}

    async def test_las_facultades_se_acotan_al_periodo(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        # `ARQUITECTURA Y URBANISMO` en 2026-1 y la unidad tecnologica en 2026-2:
        # cada periodo tiene una facultad distinta.
        await self._cargar(cliente, cabeceras_admin, "2026-1")
        await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("tec.xlsx", _pao_de_tecnologia(identificacion=OTRA_CEDULA))},
            data={"semestre": "2026-2", "actualizar_existentes": "true"},
        )
        por_codigo = await self._periodos(cliente, cabeceras_admin)

        de_2026_1 = (
            await cliente.get(
                "/api/v1/reportes/distributivo/ambito",
                headers=cabeceras_admin,
                params={"pao_ids": por_codigo["261651"]},
            )
        ).json()
        de_2026_2 = (
            await cliente.get(
                "/api/v1/reportes/distributivo/ambito",
                headers=cabeceras_admin,
                params={"pao_ids": por_codigo["262151"]},
            )
        ).json()

        assert [f["codigo"] for f in de_2026_1["facultades"]] == ["FAU"]
        assert [f["codigo"] for f in de_2026_2["facultades"]] == ["UAEFTT"]

    async def test_las_carreras_se_acotan_a_la_facultad(self, sembrado, cabeceras_admin) -> None:
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-1")
        await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("tec.xlsx", _pao_de_tecnologia(identificacion=OTRA_CEDULA))},
            data={"semestre": "2026-1", "actualizar_existentes": "true"},
        )
        por_codigo = await self._periodos(cliente, cabeceras_admin)
        periodos = [por_codigo["261651"], por_codigo["261151"]]

        sin_facultad = (
            await cliente.get(
                "/api/v1/reportes/distributivo/ambito",
                headers=cabeceras_admin,
                params={"pao_ids": periodos},
            )
        ).json()
        assert len(sin_facultad["facultades"]) == 2
        assert len(sin_facultad["carreras"]) == 2

        fau = next(f for f in sin_facultad["facultades"] if f["codigo"] == "FAU")
        con_facultad = (
            await cliente.get(
                "/api/v1/reportes/distributivo/ambito",
                headers=cabeceras_admin,
                params={"pao_ids": periodos, "facultad_ids": fau["id"]},
            )
        ).json()

        # La facultad marcada acota las carreras, pero **no** la lista de
        # facultades: si se acotara a si misma, desmarcarla seria imposible.
        assert len(con_facultad["facultades"]) == 2
        assert [c["codigo"] for c in con_facultad["carreras"]] == [
            "UIO:ARQUITECTURA - GRADO - PRESENCIAL"
        ]

    async def test_sin_periodos_no_acota_nada(self, sembrado, cabeceras_admin) -> None:
        """Es la pantalla la que no pregunta hasta que haya un periodo marcado."""
        _, cliente = sembrado
        await self._cargar(cliente, cabeceras_admin, "2026-1")

        cuerpo = (
            await cliente.get("/api/v1/reportes/distributivo/ambito", headers=cabeceras_admin)
        ).json()

        assert len(cuerpo["facultades"]) == 1


class TestExportarDelTablero:
    """Las dos tablas del tablero, tambien como archivo.

    Salen del mismo caso de uso que la pantalla —`ObtenerTableroDistributivo`—
    y no de una consulta paralela: dos caminos al mismo numero acaban
    divergiendo, y entonces nadie sabe cual creer.
    """

    async def _preparar(self, cliente, cabeceras) -> None:  # type: ignore[no-untyped-def]
        carga = TestTableroDelDistributivo()
        await carga._cargar(cliente, cabeceras, "2026-1", estado="Validación Pendiente")
        await carga._cargar(cliente, cabeceras, "2026-2")

    @pytest.mark.parametrize("resumen", ["aprobacion", "comparativo"])
    async def test_los_dos_resumenes_del_tablero(
        self, sembrado, cabeceras_admin, resumen: str
    ) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            f"/api/v1/distributivo/resumenes/exportar?resumen={resumen}&formato=XLSX",
            headers=cabeceras_admin,
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.content.startswith(b"PK")

    async def test_el_desglose_por_estado_lista_los_cinco_siempre(
        self, sembrado, cabeceras_admin
    ) -> None:
        """Que «Con error» valga cero es justamente lo que se quiere leer."""
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar?resumen=comparativo&formato=CSV",
            headers=cabeceras_admin,
        )
        texto = respuesta.content.decode("utf-8-sig")

        for etiqueta in (
            "Validado",
            "Validado con excepcion",
            "Validacion pendiente",
            "Con error",
            "Sin estado registrado",
        ):
            assert etiqueta in texto, etiqueta

    async def test_las_columnas_llevan_el_semestre_y_no_los_codigos(
        self, sembrado, cabeceras_admin
    ) -> None:
        """Un grupo son hasta seis codigos: no caben en una cabecera."""
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar?resumen=aprobacion&formato=CSV",
            headers=cabeceras_admin,
        )
        texto = respuesta.content.decode("utf-8-sig")

        assert "Filas 2026-2" in texto
        assert "Filas 2026-1" in texto
        assert "Variacion (puntos)" in texto
        # Los codigos van en el subtitulo y en la constancia de filtros.
        assert "262651" in texto
        assert "261651" in texto

    async def test_se_puede_titular_cada_grupo_a_mano(self, sembrado, cabeceras_admin) -> None:
        """Un grupo puede reunir periodos de varios semestres: el rotulo se edita."""
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)

        respuesta = await cliente.get(
            "/api/v1/distributivo/resumenes/exportar",
            headers=cabeceras_admin,
            params={
                "resumen": "aprobacion",
                "formato": "CSV",
                "etiqueta_a": "Antes",
                "etiqueta_b": "Ahora",
            },
        )
        texto = respuesta.content.decode("utf-8-sig")

        assert "Filas Ahora" in texto
        assert "Filas Antes" in texto
        assert "Filas 2026-2" not in texto

    async def test_el_tablero_acepta_grupos_de_varios_periodos(
        self, sembrado, cabeceras_admin
    ) -> None:
        _, cliente = sembrado
        await self._preparar(cliente, cabeceras_admin)
        await cliente.post(
            "/api/v1/distributivo/importaciones/pao",
            headers=cabeceras_admin,
            files={"archivo": ("tec.xlsx", _pao_de_tecnologia(identificacion=OTRA_CEDULA))},
            data={"semestre": "2026-2", "actualizar_existentes": "true"},
        )

        cuerpo = (await cliente.get("/api/v1/distributivo/tablero", headers=cabeceras_admin)).json()

        # 2026-2 son ahora dos periodos —grado y tecnologia— y el grupo los
        # reune: es lo que distingue comparar semestres de comparar periodos.
        assert sorted(cuerpo["actual"]["codigos"]) == ["262151", "262651"]
        assert cuerpo["actual"]["total"] == 2
        assert cuerpo["anterior"]["codigos"] == ["261651"]
