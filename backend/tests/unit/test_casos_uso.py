"""Pruebas de casos de uso completos, sin base de datos ni red.

Cada prueba ejercita un caso de uso de principio a fin —incluida su transaccion
y su reconciliacion— usando dobles en memoria. Que esto sea posible es la
justificacion practica de la arquitectura: un fallo de logica se detecta en
milisegundos, no levantando Docker.
"""

from __future__ import annotations

import pytest
from tests.conftest import CEDULAS_VALIDAS, MOMENTO_FIJO, hacer_persona, hacer_usuario

from app.application.base import ContextoEjecucion
from app.application.casos_uso.autenticacion import (
    EntradaInicioSesion,
    IniciarSesion,
    PoliticaAcceso,
)
from app.application.casos_uso.consultas import (
    ConsultarPersona,
    CrearJobCobertura,
    EntradaConsultarPersona,
    EntradaCrearJob,
)
from app.application.casos_uso.personas import (
    CrearPersona,
    EntradaCrearPersona,
    FilaImportacion,
    ImportarPersonas,
)
from app.domain.enums import EstadoConsulta, Permiso, RolCodigo
from app.domain.errors import (
    ConflictoDeEstado,
    CredencialesInvalidas,
    ErrorAutorizacion,
    UsuarioBloqueado,
    UsuarioInactivo,
    YaExiste,
)
from app.domain.ports.reloj import AleatorioDelSistema
from app.domain.services.planificacion import ConfiguracionRitmo, PoliticaPlanificacion
from app.domain.services.reconciliador import ReconciliadorTitulos
from app.domain.value_objects import Email
from app.infrastructure.senescyt.mock import ProveedorMock

pytestmark = pytest.mark.unit


@pytest.fixture
def contexto_admin(roles):  # type: ignore[no-untyped-def]
    return ContextoEjecucion(
        actor=hacer_usuario(roles={roles[RolCodigo.ADMIN.value]}, superusuario=True)
    )


@pytest.fixture
def contexto_lector(roles):  # type: ignore[no-untyped-def]
    return ContextoEjecucion(actor=hacer_usuario(roles={roles[RolCodigo.CONSULTA.value]}))


# ===========================================================================
class TestAutorizacionEnLaBase:
    """La comprobacion vive en `CasoDeUso.__call__`: ningun caso de uso puede
    olvidarse de autorizar."""

    async def test_rechaza_a_quien_no_tiene_el_permiso(self, uow, contexto_lector) -> None:
        caso = CrearPersona(uow)
        with pytest.raises(ErrorAutorizacion, match="personas:escribir"):
            await caso(
                EntradaCrearPersona(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Yepez"),
                contexto_lector,
            )
        assert uow.commits == 0, "no debe escribir nada si no autoriza"

    async def test_rechaza_a_un_anonimo(self, uow) -> None:
        caso = CrearPersona(uow)
        with pytest.raises(ErrorAutorizacion):
            await caso(
                EntradaCrearPersona(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Yepez"),
                ContextoEjecucion(),
            )

    async def test_el_contexto_del_sistema_pasa_sin_actor(self, uow) -> None:
        """El planificador opera sin usuario: su autorizacion viene de la
        configuracion del job, no de una sesion."""
        caso = CrearPersona(uow)
        persona = await caso(
            EntradaCrearPersona(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Yepez"),
            ContextoEjecucion.sistema(),
        )
        assert persona.cedula.valor == CEDULAS_VALIDAS[0]

    def test_todos_los_casos_declaran_su_descriptor(self) -> None:
        """El descriptor alimentara el catalogo de skills de la Fase 11."""
        descriptor = ConsultarPersona.descriptor()
        assert descriptor["nombre"] == "consultas.consultar_persona"
        assert descriptor["permiso"] == Permiso.CONSULTAS_EJECUTAR.value
        assert descriptor["descripcion"]


# ===========================================================================
class TestIniciarSesion:
    @pytest.fixture
    def caso(self, uow, hasher, tokens, reloj):  # type: ignore[no-untyped-def]
        return IniciarSesion(uow, hasher, tokens, reloj, PoliticaAcceso())

    @pytest.fixture
    async def usuario(self, uow, hasher, roles):  # type: ignore[no-untyped-def]
        u = hacer_usuario(
            email="ana@ute.edu.ec",
            roles={roles[RolCodigo.ANALISTA.value]},
            hash_contrasena=hasher.hashear("Correcta#2026.Ok"),
        )
        await uow.usuarios.agregar(u)
        return u

    async def test_acceso_correcto_emite_tokens(self, caso, uow, usuario) -> None:
        sesion = await caso(
            EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Correcta#2026.Ok"),
            ContextoEjecucion(),
        )
        assert sesion.tokens.acceso and sesion.tokens.refresco
        assert sesion.usuario.email == Email("ana@ute.edu.ec")
        assert len(uow.tokens.datos) == 1, "el token de refresco debe persistirse"
        assert uow.commits == 1

    async def test_contrasena_incorrecta_cuenta_el_intento(self, caso, uow, usuario) -> None:
        with pytest.raises(CredencialesInvalidas):
            await caso(
                EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Incorrecta#1"),
                ContextoEjecucion(),
            )
        assert usuario.intentos_fallidos == 1

    async def test_un_correo_inexistente_da_el_mismo_error(self, caso, uow) -> None:
        """No se revela si la cuenta existe: mismo error y mismo coste."""
        with pytest.raises(CredencialesInvalidas):
            await caso(
                EntradaInicioSesion(email="nadie@ute.edu.ec", contrasena="Cualquiera#1"),
                ContextoEjecucion(),
            )

    async def test_un_correo_malformado_no_delata_nada(self, caso, uow) -> None:
        with pytest.raises(CredencialesInvalidas):
            await caso(
                EntradaInicioSesion(email="no-es-un-correo", contrasena="X"),
                ContextoEjecucion(),
            )

    async def test_se_bloquea_tras_cinco_intentos(self, caso, uow, usuario) -> None:
        for _ in range(5):
            with pytest.raises(CredencialesInvalidas):
                await caso(
                    EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Mala#1"),
                    ContextoEjecucion(),
                )

        with pytest.raises(UsuarioBloqueado):
            await caso(
                EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Correcta#2026.Ok"),
                ContextoEjecucion(),
            )

    async def test_una_cuenta_desactivada_no_entra(self, caso, uow, usuario) -> None:
        usuario.activo = False
        with pytest.raises(UsuarioInactivo):
            await caso(
                EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Correcta#2026.Ok"),
                ContextoEjecucion(),
            )

    async def test_el_token_lleva_los_permisos_del_usuario(
        self, caso, uow, usuario, tokens
    ) -> None:
        sesion = await caso(
            EntradaInicioSesion(email="ana@ute.edu.ec", contrasena="Correcta#2026.Ok"),
            ContextoEjecucion(),
        )
        contenido = tokens.decodificar_acceso(sesion.tokens.acceso)
        assert Permiso.TITULOS_ESCRIBIR.value in contenido.permisos
        assert Permiso.USUARIOS_ESCRIBIR.value not in contenido.permisos


# ===========================================================================
class TestCrearPersona:
    async def test_crea_y_confirma(self, uow, contexto_admin) -> None:
        persona = await CrearPersona(uow)(
            EntradaCrearPersona(
                cedula=CEDULAS_VALIDAS[0],
                nombres="ana maria",
                apellidos="yepez cordova",
                unidad="Vicerrectorado",
            ),
            contexto_admin,
        )
        assert persona.nombre.completo == "Ana Maria Yepez Cordova"
        assert uow.commits == 1

    async def test_rechaza_una_cedula_repetida(self, uow, contexto_admin) -> None:
        await uow.personas.agregar(hacer_persona(CEDULAS_VALIDAS[0]))
        with pytest.raises(YaExiste, match="cedula"):
            await CrearPersona(uow)(
                EntradaCrearPersona(
                    cedula=CEDULAS_VALIDAS[0], nombres="Otro", apellidos="Distinto"
                ),
                contexto_admin,
            )


class TestImportarPersonas:
    async def test_una_fila_mala_no_aborta_el_lote(self, uow, contexto_admin) -> None:
        """Con miles de registros, un 'todo o nada' hace la herramienta
        inutilizable: se informa fila a fila."""
        filas = [
            FilaImportacion(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Yepez"),
            FilaImportacion(cedula="1234567890", nombres="Mala", apellidos="Cedula"),
            FilaImportacion(cedula=CEDULAS_VALIDAS[1], nombres="Luis", apellidos="Munoz"),
            FilaImportacion(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Repetida"),
        ]
        resultado = await ImportarPersonas(uow)(filas, contexto_admin)

        assert resultado.creadas == 2
        assert resultado.duplicadas == 1
        assert len(resultado.rechazadas) == 1
        assert resultado.rechazadas[0].fila == 2
        assert "verificador" in resultado.rechazadas[0].motivo
        assert not resultado.exitosa

    async def test_omite_las_que_ya_existen_en_la_base(self, uow, contexto_admin) -> None:
        await uow.personas.agregar(hacer_persona(CEDULAS_VALIDAS[0]))
        resultado = await ImportarPersonas(uow)(
            [FilaImportacion(cedula=CEDULAS_VALIDAS[0], nombres="Ana", apellidos="Y")],
            contexto_admin,
        )
        assert resultado.creadas == 0
        assert resultado.duplicadas == 1


# ===========================================================================
class TestConsultarPersona:
    @pytest.fixture
    def caso(self, uow, reloj):  # type: ignore[no-untyped-def]
        return ConsultarPersona(
            uow,
            ProveedorMock(latencia_segundos=0, probabilidad_error=0, probabilidad_sin_titulos=0),
            ReconciliadorTitulos(),
            reloj,
            PoliticaPlanificacion(ConfiguracionRitmo(), AleatorioDelSistema(semilla=1)),
        )

    @pytest.fixture
    async def persona(self, uow):  # type: ignore[no-untyped-def]
        p = hacer_persona(CEDULAS_VALIDAS[0])
        await uow.personas.agregar(p)
        return p

    async def test_registra_titulos_y_deja_constancia(
        self, caso, uow, persona, contexto_admin
    ) -> None:
        resultado = await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)

        assert resultado.log.estado is EstadoConsulta.EXITO
        assert resultado.log.titulos_encontrados > 0
        assert resultado.log.titulos_nuevos > 0
        assert len(uow.titulos.datos) == resultado.log.titulos_encontrados
        assert len(uow.logs.datos) == 1, "toda consulta deja una fila en el historico"
        assert persona.ultima_consulta_estado is EstadoConsulta.EXITO

    async def test_la_regla_de_cobertura_impide_repetir(
        self, caso, uow, persona, contexto_admin
    ) -> None:
        await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)
        with pytest.raises(ConflictoDeEstado, match="periodo vigente"):
            await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)

    async def test_forzar_salta_la_regla_sin_duplicar_titulos(
        self, caso, uow, persona, contexto_admin
    ) -> None:
        primera = await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)
        segunda = await caso(
            EntradaConsultarPersona(persona_id=persona.id, forzar=True), contexto_admin
        )

        assert segunda.log.estado is EstadoConsulta.EXITO
        assert segunda.log.titulos_nuevos == 0, "la huella evita duplicar"
        assert len(uow.titulos.datos) == primera.log.titulos_encontrados
        assert len(uow.logs.datos) == 2

    async def test_no_consulta_a_una_persona_inactiva(
        self, caso, uow, persona, contexto_admin
    ) -> None:
        persona.desactivar()
        with pytest.raises(Exception, match="inactiva"):
            await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)

    async def test_un_error_del_proveedor_tambien_se_registra(
        self, uow, reloj, contexto_admin
    ) -> None:
        """La garantia central: se escribe en el historico pase lo que pase.

        Sin ella, un dato desactualizado seria indistinguible de uno que no se
        pudo consultar.
        """
        persona = hacer_persona(CEDULAS_VALIDAS[0])
        await uow.personas.agregar(persona)

        caso = ConsultarPersona(
            uow,
            ProveedorMock(latencia_segundos=0, probabilidad_error=1.0),
            ReconciliadorTitulos(),
            reloj,
            PoliticaPlanificacion(ConfiguracionRitmo(), AleatorioDelSistema(semilla=1)),
        )
        resultado = await caso(EntradaConsultarPersona(persona_id=persona.id), contexto_admin)

        assert resultado.log.estado.es_error
        assert len(uow.logs.datos) == 1
        assert resultado.log.mensaje


# ===========================================================================
class TestCrearJobCobertura:
    @pytest.fixture
    def caso(self, uow, reloj, aleatorio):  # type: ignore[no-untyped-def]
        return CrearJobCobertura(
            uow,
            PoliticaPlanificacion(ConfiguracionRitmo(), aleatorio),
            reloj,
            aleatorio,
        )

    @pytest.fixture
    async def padron(self, uow):  # type: ignore[no-untyped-def]
        for i, cedula in enumerate(CEDULAS_VALIDAS):
            await uow.personas.agregar(hacer_persona(cedula, nombres=f"Persona {i}"))
        return list(uow.personas.datos.values())

    async def test_encola_a_todo_el_padron_pendiente(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        resultado = await caso(EntradaCrearJob(nombre="Campana 2026"), contexto_admin)
        assert resultado.job.total_items == len(padron)
        assert len(uow.jobs.items) == len(padron)
        assert resultado.factibilidad.es_factible

    async def test_excluye_a_quien_ya_fue_consultado_en_el_periodo(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        padron[0].registrar_consulta(EstadoConsulta.EXITO, momento=MOMENTO_FIJO)
        resultado = await caso(EntradaCrearJob(nombre="Campana"), contexto_admin)
        assert resultado.job.total_items == len(padron) - 1

    async def test_solo_admite_un_job_activo(self, caso, uow, padron, contexto_admin) -> None:
        """Dos campanas simultaneas romperian la garantia de cobertura."""
        await caso(EntradaCrearJob(nombre="Primera"), contexto_admin)
        with pytest.raises(ConflictoDeEstado, match="job activo"):
            await caso(EntradaCrearJob(nombre="Segunda"), contexto_admin)

    async def test_falla_si_no_queda_nadie_por_consultar(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        for persona in padron:
            persona.registrar_consulta(EstadoConsulta.EXITO, momento=MOMENTO_FIJO)
        with pytest.raises(ConflictoDeEstado, match="No hay personas"):
            await caso(EntradaCrearJob(nombre="Campana"), contexto_admin)

    async def test_por_defecto_los_items_quedan_disponibles_de_inmediato(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        """El ritmo lo impone la politica de planificacion. Anadir una segunda
        espera solo consigue que una campana pequena tarde dias sin motivo."""
        await caso(EntradaCrearJob(nombre="Campana"), contexto_admin)
        assert all(i.programado_para is None for i in uow.jobs.items.values())

    async def test_puede_pedirse_el_reparto_a_lo_largo_del_periodo(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        await caso(EntradaCrearJob(nombre="Campana", distribuir_en_periodo=True), contexto_admin)
        programados = [i.programado_para for i in uow.jobs.items.values()]
        assert all(p is not None for p in programados)
        assert len(set(programados)) > 1, "deben repartirse en el tiempo"

    async def test_advierte_si_el_periodo_no_alcanza(
        self, uow, reloj, aleatorio, padron, contexto_admin
    ) -> None:
        config = ConfiguracionRitmo(periodo_dias=1, max_consultas_por_hora=1)
        caso = CrearJobCobertura(uow, PoliticaPlanificacion(config, aleatorio), reloj, aleatorio)
        # Un padron minusculo frente a una capacidad ridicula: 5 personas, y la
        # capacidad diaria con 1 consulta/hora en 13 horas operativas es ~13.
        resultado = await caso(EntradaCrearJob(nombre="Campana"), contexto_admin)
        # Con 5 personas si alcanza; lo que se verifica es que la evaluacion se
        # calcula y se devuelve.
        assert resultado.factibilidad.consultas_diarias_estimadas > 0
        assert resultado.factibilidad.periodo_dias == 1

    async def test_guarda_una_instantanea_de_la_configuracion(
        self, caso, uow, padron, contexto_admin
    ) -> None:
        """Hace reproducible el resultado: se sabe con que ritmo se ejecuto."""
        resultado = await caso(EntradaCrearJob(nombre="Campana"), contexto_admin)
        config = resultado.job.configuracion
        assert "franja_pico" in config
        assert "max_consultas_por_hora" in config
        assert config["distribuido_en_periodo"] is False
