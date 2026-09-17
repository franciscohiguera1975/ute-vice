"""Dobles de prueba en memoria.

Que estos dobles sean posibles —y cortos— es la prueba practica de que la
arquitectura funciona: los casos de uso dependen de puertos, asi que se pueden
ejercitar enteros sin PostgreSQL, sin red y sin Docker. Una prueba de un caso de
uso corre en milisegundos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from app.domain.entities.auth import Rol, TokenRefresco, Usuario
from app.domain.entities.consulta import ConsultaLog, ItemJob, JobCobertura
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import (
    PERMISOS_POR_ROL,
    AuthProvider,
    EstadoItemJob,
    EstadoJob,
)
from app.domain.ports.repositorios import (
    FiltroLogs,
    FiltroPersonas,
    FiltroTitulos,
    Pagina,
    Paginacion,
)
from app.domain.value_objects import Cedula, Email, NombrePersona

MOMENTO_FIJO = datetime(2026, 9, 4, 14, 30, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Repositorios en memoria
# ---------------------------------------------------------------------------


def _paginar(items: list[Any], paginacion: Paginacion) -> Pagina[Any]:
    inicio = paginacion.offset
    return Pagina(
        items=items[inicio : inicio + paginacion.limite],
        total=len(items),
        pagina=paginacion.pagina,
        tamano=paginacion.tamano,
    )


class RepoUsuarios:
    def __init__(self) -> None:
        self.datos: dict[UUID, Usuario] = {}

    async def obtener(self, usuario_id: UUID) -> Usuario | None:
        return self.datos.get(usuario_id)

    async def obtener_por_email(self, email: Email) -> Usuario | None:
        return next((u for u in self.datos.values() if u.email == email), None)

    async def obtener_por_externo(self, proveedor: str, identificador: str) -> Usuario | None:
        return next(
            (
                u
                for u in self.datos.values()
                if u.proveedor.value == proveedor and u.identificador_externo == identificador
            ),
            None,
        )

    async def listar(
        self, paginacion: Paginacion, *, texto=None, activo=None, rol=None
    ) -> Pagina[Usuario]:
        items = list(self.datos.values())
        if activo is not None:
            items = [u for u in items if u.activo == activo]
        if rol:
            items = [u for u in items if u.tiene_rol(rol)]
        if texto:
            t = texto.lower()
            items = [u for u in items if t in u.nombre_completo.lower() or t in u.email.valor]
        return _paginar(items, paginacion)

    async def agregar(self, usuario: Usuario) -> Usuario:
        self.datos[usuario.id] = usuario
        return usuario

    async def actualizar(self, usuario: Usuario) -> Usuario:
        self.datos[usuario.id] = usuario
        return usuario

    async def eliminar(self, usuario_id: UUID) -> None:
        self.datos.pop(usuario_id, None)

    async def existe_email(self, email: Email, *, excluyendo: UUID | None = None) -> bool:
        return any(u.email == email and u.id != excluyendo for u in self.datos.values())

    async def contar_superusuarios_activos(self) -> int:
        return sum(1 for u in self.datos.values() if u.es_superusuario and u.activo)


class RepoRoles:
    def __init__(self) -> None:
        self.datos: dict[str, Rol] = {}

    async def obtener(self, rol_id: UUID) -> Rol | None:
        return next((r for r in self.datos.values() if r.id == rol_id), None)

    async def obtener_por_codigo(self, codigo: str) -> Rol | None:
        return self.datos.get(codigo.upper())

    async def listar_todos(self) -> list[Rol]:
        return sorted(self.datos.values(), key=lambda r: r.codigo)

    async def agregar(self, rol: Rol) -> Rol:
        self.datos[rol.codigo] = rol
        return rol

    async def actualizar(self, rol: Rol) -> Rol:
        self.datos[rol.codigo] = rol
        return rol

    async def eliminar(self, rol_id: UUID) -> None:
        rol = await self.obtener(rol_id)
        if rol:
            self.datos.pop(rol.codigo, None)

    async def contar_usuarios(self, rol_id: UUID) -> int:
        return 0


class RepoTokens:
    def __init__(self) -> None:
        self.datos: dict[str, TokenRefresco] = {}

    async def obtener_por_hash(self, hash_token: str) -> TokenRefresco | None:
        return self.datos.get(hash_token)

    async def agregar(self, token: TokenRefresco) -> TokenRefresco:
        self.datos[token.hash_token] = token
        return token

    async def actualizar(self, token: TokenRefresco) -> TokenRefresco:
        self.datos[token.hash_token] = token
        return token

    async def revocar_todos_de(self, usuario_id: UUID) -> int:
        contador = 0
        for token in self.datos.values():
            if token.usuario_id == usuario_id and not token.esta_revocado:
                token.revocar()
                contador += 1
        return contador

    async def eliminar_expirados(self, antes_de: datetime) -> int:
        vencidos = [h for h, t in self.datos.items() if t.expira_en < antes_de]
        for h in vencidos:
            del self.datos[h]
        return len(vencidos)


class RepoPersonas:
    def __init__(self) -> None:
        self.datos: dict[UUID, Persona] = {}

    async def obtener(self, persona_id: UUID) -> Persona | None:
        return self.datos.get(persona_id)

    async def obtener_por_cedula(self, cedula: Cedula) -> Persona | None:
        return next((p for p in self.datos.values() if p.cedula == cedula), None)

    async def listar(self, filtro: FiltroPersonas, paginacion: Paginacion) -> Pagina[Persona]:
        items = list(self.datos.values())
        if filtro.activo is not None:
            items = [p for p in items if p.activo == filtro.activo]
        if filtro.texto:
            t = filtro.texto.lower()
            items = [p for p in items if t in p.clave_busqueda]
        if filtro.con_titulos is not None:
            items = [p for p in items if (p.titulos_registrados > 0) == filtro.con_titulos]
        if filtro.nunca_consultadas:
            items = [p for p in items if p.nunca_consultada]
        return _paginar(items, paginacion)

    async def agregar(self, persona: Persona) -> Persona:
        self.datos[persona.id] = persona
        return persona

    async def agregar_muchas(self, personas: list[Persona]) -> int:
        for p in personas:
            self.datos[p.id] = p
        return len(personas)

    async def actualizar(self, persona: Persona) -> Persona:
        self.datos[persona.id] = persona
        return persona

    async def eliminar(self, persona_id: UUID) -> None:
        self.datos.pop(persona_id, None)

    async def existe_cedula(self, cedula: Cedula, *, excluyendo: UUID | None = None) -> bool:
        return any(p.cedula == cedula and p.id != excluyendo for p in self.datos.values())

    async def seleccionar_para_cobertura(
        self, *, desde: datetime, hasta: datetime, limite: int | None = None
    ) -> list[Persona]:
        candidatas = [
            p
            for p in self.datos.values()
            if p.activo
            and (
                p.ultima_consulta_en is None
                or p.ultima_consulta_en < desde
                or (p.ultima_consulta_estado and p.ultima_consulta_estado.es_error)
            )
        ]
        return candidatas[:limite] if limite else candidatas

    async def contar_activas(self) -> int:
        return sum(1 for p in self.datos.values() if p.activo)


class RepoTitulos:
    def __init__(self) -> None:
        self.datos: dict[UUID, Titulo] = {}

    async def obtener(self, titulo_id: UUID) -> Titulo | None:
        return self.datos.get(titulo_id)

    async def listar(self, filtro: FiltroTitulos, paginacion: Paginacion) -> Pagina[Titulo]:
        items = list(self.datos.values())
        if filtro.persona_id:
            items = [t for t in items if t.persona_id == filtro.persona_id]
        if filtro.nivel:
            items = [t for t in items if t.nivel == filtro.nivel]
        if filtro.estado:
            items = [t for t in items if t.estado == filtro.estado]
        return _paginar(items, paginacion)

    async def listar_por_persona(
        self, persona_id: UUID, *, incluir_retirados: bool = True
    ) -> list[Titulo]:
        from app.domain.enums import EstadoTitulo

        items = [t for t in self.datos.values() if t.persona_id == persona_id]
        if not incluir_retirados:
            items = [t for t in items if t.estado is not EstadoTitulo.RETIRADO]
        return items

    async def agregar(self, titulo: Titulo) -> Titulo:
        self.datos[titulo.id] = titulo
        return titulo

    async def agregar_muchos(self, titulos: list[Titulo]) -> int:
        for t in titulos:
            self.datos[t.id] = t
        return len(titulos)

    async def actualizar(self, titulo: Titulo) -> Titulo:
        self.datos[titulo.id] = titulo
        return titulo

    async def actualizar_muchos(self, titulos: list[Titulo]) -> int:
        for t in titulos:
            self.datos[t.id] = t
        return len(titulos)

    async def eliminar(self, titulo_id: UUID) -> None:
        self.datos.pop(titulo_id, None)

    async def contar_por_persona(self, persona_id: UUID) -> int:
        return sum(1 for t in self.datos.values() if t.persona_id == persona_id)


class RepoLogs:
    def __init__(self) -> None:
        self.datos: list[ConsultaLog] = []

    async def obtener(self, log_id: UUID) -> ConsultaLog | None:
        return next((registro for registro in self.datos if registro.id == log_id), None)

    async def listar(self, filtro: FiltroLogs, paginacion: Paginacion) -> Pagina[ConsultaLog]:
        items = list(self.datos)
        if filtro.persona_id:
            items = [registro for registro in items if registro.persona_id == filtro.persona_id]
        if filtro.solo_errores:
            items = [registro for registro in items if registro.estado.es_error]
        if filtro.solo_con_cambios:
            items = [registro for registro in items if registro.hubo_cambios]
        return _paginar(items, paginacion)

    async def agregar(self, log: ConsultaLog) -> ConsultaLog:
        self.datos.append(log)
        return log

    async def ultimo_de_persona(self, persona_id: UUID) -> ConsultaLog | None:
        registros = [r for r in self.datos if r.persona_id == persona_id]
        return registros[-1] if registros else None

    async def contar_en_ventana(self, desde: datetime, hasta: datetime) -> int:
        return sum(1 for r in self.datos if desde <= r.iniciado_en <= hasta)


class RepoJobs:
    def __init__(self) -> None:
        self.jobs: dict[UUID, JobCobertura] = {}
        self.items: dict[UUID, ItemJob] = {}

    async def obtener(self, job_id: UUID) -> JobCobertura | None:
        return self.jobs.get(job_id)

    async def listar(self, paginacion: Paginacion, *, estado=None) -> Pagina[JobCobertura]:
        items = list(self.jobs.values())
        if estado:
            items = [j for j in items if j.estado == estado]
        return _paginar(items, paginacion)

    async def job_activo(self) -> JobCobertura | None:
        return next(
            (
                j
                for j in self.jobs.values()
                if j.estado in {EstadoJob.PROGRAMADO, EstadoJob.EN_CURSO, EstadoJob.PAUSADO}
            ),
            None,
        )

    async def agregar(self, job: JobCobertura) -> JobCobertura:
        self.jobs[job.id] = job
        return job

    async def actualizar(self, job: JobCobertura) -> JobCobertura:
        self.jobs[job.id] = job
        return job

    async def agregar_items(self, items: list[ItemJob]) -> int:
        for i in items:
            self.items[i.id] = i
        return len(items)

    async def obtener_item(self, item_id: UUID) -> ItemJob | None:
        return self.items.get(item_id)

    async def obtener_item_por_desafio(self, desafio_id: str) -> ItemJob | None:
        return next((i for i in self.items.values() if i.desafio_id == desafio_id), None)

    async def siguiente_item(self, job_id: UUID, *, ahora: datetime) -> ItemJob | None:
        listos = [i for i in self.items.values() if i.job_id == job_id and i.esta_listo(ahora)]
        return min(listos, key=lambda i: i.orden) if listos else None

    async def actualizar_item(self, item: ItemJob) -> ItemJob:
        self.items[item.id] = item
        return item

    async def listar_items(self, job_id: UUID, paginacion: Paginacion, *, estado=None):
        items = [i for i in self.items.values() if i.job_id == job_id]
        if estado:
            items = [i for i in items if i.estado.value == estado]
        return _paginar(items, paginacion)

    async def contar_items_pendientes(self, job_id: UUID) -> int:
        return sum(
            1
            for i in self.items.values()
            if i.job_id == job_id
            and i.estado in {EstadoItemJob.PENDIENTE, EstadoItemJob.EN_PROCESO}
        )


class RepoCatalogos:
    """Los doce catalogos en memoria, indexados por tipo."""

    def __init__(self) -> None:
        from app.domain.entities.catalogo import TipoCatalogo

        self.datos: dict[TipoCatalogo, dict[UUID, Any]] = {t: {} for t in TipoCatalogo}
        self.referencias: dict[UUID, int] = {}

    async def obtener(self, tipo, elemento_id: UUID):  # type: ignore[no-untyped-def]
        return self.datos[tipo].get(elemento_id)

    async def obtener_por_codigo(self, tipo, codigo: str):  # type: ignore[no-untyped-def]
        clave = " ".join((codigo or "").split()).upper()
        return next((e for e in self.datos[tipo].values() if e.codigo == clave), None)

    async def listar(self, tipo, filtro, paginacion):  # type: ignore[no-untyped-def]
        items = list(self.datos[tipo].values())
        if filtro.activo is not None:
            items = [e for e in items if e.activo == filtro.activo]
        if filtro.texto:
            from app.domain.value_objects import normalizar_texto

            patron = normalizar_texto(filtro.texto)
            items = [e for e in items if patron in e.clave_busqueda]
        return _paginar(items, paginacion)

    async def listar_todos(self, tipo, *, solo_activos: bool = True):  # type: ignore[no-untyped-def]
        items = list(self.datos[tipo].values())
        if solo_activos:
            items = [e for e in items if e.activo]
        return sorted(items, key=lambda e: (e.orden, e.nombre))

    async def agregar(self, elemento):  # type: ignore[no-untyped-def]
        self.datos[elemento.tipo][elemento.id] = elemento
        return elemento

    async def agregar_muchos(self, elementos) -> int:  # type: ignore[no-untyped-def]
        for e in elementos:
            self.datos[e.tipo][e.id] = e
        return len(elementos)

    async def actualizar(self, elemento):  # type: ignore[no-untyped-def]
        self.datos[elemento.tipo][elemento.id] = elemento
        return elemento

    async def eliminar(self, tipo, elemento_id: UUID) -> None:  # type: ignore[no-untyped-def]
        self.datos[tipo].pop(elemento_id, None)

    async def existe_codigo(self, tipo, codigo: str, *, excluyendo=None) -> bool:  # type: ignore[no-untyped-def]
        clave = " ".join((codigo or "").split()).upper()
        return any(e.codigo == clave and e.id != excluyendo for e in self.datos[tipo].values())

    async def contar_referencias(self, tipo, elemento_id: UUID) -> int:  # type: ignore[no-untyped-def]
        return self.referencias.get(elemento_id, 0)


class RepoDocentes:
    def __init__(self) -> None:
        self.datos: dict[UUID, Any] = {}

    async def obtener(self, docente_id: UUID):  # type: ignore[no-untyped-def]
        return self.datos.get(docente_id)

    async def obtener_por_identificacion(self, identificacion: str):  # type: ignore[no-untyped-def]
        clave = identificacion.strip().upper()
        return next((d for d in self.datos.values() if d.identificacion.valor == clave), None)

    async def listar(self, filtro, paginacion):  # type: ignore[no-untyped-def]
        items = list(self.datos.values())
        if filtro.activo is not None:
            items = [d for d in items if d.activo == filtro.activo]
        if filtro.solo_con_pasaporte:
            items = [d for d in items if not d.identificacion.es_cedula]
        if filtro.texto:
            from app.domain.value_objects import normalizar_texto

            patron = normalizar_texto(filtro.texto)
            items = [d for d in items if patron in d.clave_busqueda]
        return _paginar(items, paginacion)

    async def agregar(self, docente):  # type: ignore[no-untyped-def]
        self.datos[docente.id] = docente
        return docente

    async def agregar_muchos(self, docentes) -> int:  # type: ignore[no-untyped-def]
        for d in docentes:
            self.datos[d.id] = d
        return len(docentes)

    async def actualizar(self, docente):  # type: ignore[no-untyped-def]
        self.datos[docente.id] = docente
        return docente

    async def eliminar(self, docente_id: UUID) -> None:
        self.datos.pop(docente_id, None)

    async def existe_identificacion(self, identificacion: str, *, excluyendo=None) -> bool:  # type: ignore[no-untyped-def]
        clave = identificacion.strip().upper()
        return any(
            d.identificacion.valor == clave and d.id != excluyendo for d in self.datos.values()
        )

    async def contar_filas(self, docente_id: UUID) -> int:
        return 0

    async def titulos_de(self, docente_id: UUID):  # type: ignore[no-untyped-def]
        return []


class RepoDistributivo:
    def __init__(self) -> None:
        self.datos: dict[UUID, Any] = {}
        # Lo que devuelven las consultas de exportacion. Las pruebas las cargan
        # directamente porque derivarlas exigiria replicar las subconsultas.
        self.reporte: list[Any] = []
        self.resueltas: list[Any] = []
        # Las pruebas de alcance comprueban con que filtro se consulto: es la
        # unica forma de verificar que el recorte lo impone el caso de uso.
        self.ultimo_filtro: Any = None
        self.carreras: list[Any] = []
        self.unidades: dict[UUID, str] = {}
        # Enlaces fila -> asignaturas, tal como los dejo `enlazar_asignaturas`.
        self.asignaturas_enlazadas: dict[UUID, list[UUID]] = {}
        # La unidad de trabajo se inyecta despues de construir los repositorios:
        # el indice de materias necesita resolver docente y periodo, que viven
        # en otros dos.
        self.uow: Any = None

    async def obtener(self, fila_id: UUID):  # type: ignore[no-untyped-def]
        return self.datos.get(fila_id)

    async def _guardar_asignaturas(self, filas):  # type: ignore[no-untyped-def]
        """En memoria la lista ya viaja en la entidad: no hay nada que enlazar."""
        return None

    async def obtener_resuelta(self, fila_id: UUID):  # type: ignore[no-untyped-def]
        from app.domain.ports.distributivo import FilaDistributivoResuelta

        fila = self.datos.get(fila_id)
        if fila is None:
            return None
        return FilaDistributivoResuelta(
            fila=fila,
            docente_identificacion="1710034065",
            docente_nombre="PEREZ LUIS",
            pao="2026-1 GRADO",
            pao_semestre="2026-1",
            facultad="FCID",
            carrera="SOFTWARE",
        )

    async def listar(self, filtro, paginacion):  # type: ignore[no-untyped-def]
        self.ultimo_filtro = filtro
        return _paginar([], paginacion)

    async def agregar(self, fila):  # type: ignore[no-untyped-def]
        self.datos[fila.id] = fila
        return fila

    async def agregar_muchas(self, filas) -> int:  # type: ignore[no-untyped-def]
        for f in filas:
            self.datos[f.id] = f
        return len(filas)

    async def actualizar(self, fila):  # type: ignore[no-untyped-def]
        self.datos[fila.id] = fila
        return fila

    async def reemplazar_muchas(self, filas):  # type: ignore[no-untyped-def]
        """En memoria la clave natural se compara a mano; en SQL la impone
        la restriccion de la tabla."""

        def clave(f):  # type: ignore[no-untyped-def]
            return (f.docente_id, f.pao_id, f.carrera_id, f.sede_id)

        existentes = {clave(f): f.id for f in self.datos.values()}
        altas = cambios = 0
        for fila in filas:
            previo = existentes.get(clave(fila))
            if previo is None:
                self.datos[fila.id] = fila
                existentes[clave(fila)] = fila.id
                altas += 1
            else:
                # Se conserva el id: es lo que hace que sobrevivan las materias.
                fila.id = previo
                self.datos[previo] = fila
                cambios += 1
        return (altas, cambios)

    async def eliminar(self, fila_id: UUID) -> None:
        self.datos.pop(fila_id, None)

    async def existe_combinacion(  # type: ignore[no-untyped-def]
        self, *, docente_id, pao_id, carrera_id, sede_id=None, excluyendo=None
    ) -> bool:
        return any(
            f.docente_id == docente_id
            and f.pao_id == pao_id
            and f.carrera_id == carrera_id
            and f.sede_id == sede_id
            and f.id != excluyendo
            for f in self.datos.values()
        )

    async def resumen(self, filtro):  # type: ignore[no-untyped-def]
        from app.domain.ports.distributivo import ResumenDistributivo

        self.ultimo_filtro = filtro
        return ResumenDistributivo(total_filas=len(self.datos))

    async def filas_para_reporte(self, filtro):  # type: ignore[no-untyped-def]
        return list(self.reporte)

    async def unidades_por_docente(self):  # type: ignore[no-untyped-def]
        return dict(self.unidades)

    async def carreras_presentes(self, filtro):  # type: ignore[no-untyped-def]
        self.ultimo_filtro = filtro
        return list(self.carreras)

    async def filas_resueltas(self, filtro):  # type: ignore[no-untyped-def]
        return list(self.resueltas)

    async def filas_de_carreras(self, carreras_ids):  # type: ignore[no-untyped-def]
        return [f for f in self.datos.values() if f.carrera_id in set(carreras_ids)]

    async def indice_para_materias(self):  # type: ignore[no-untyped-def]
        from app.domain.entities.catalogo import TipoCatalogo

        indice = []
        for fila in self.datos.values():
            docente = self.uow.docentes.datos.get(fila.docente_id)
            pao = self.uow.catalogos.datos[TipoCatalogo.PAO].get(fila.pao_id)
            if docente is None or pao is None:
                continue
            indice.append((fila.id, docente.identificacion.valor, pao.codigo))
        return indice

    async def enlazar_asignaturas(self, enlaces) -> int:  # type: ignore[no-untyped-def]
        for fila_id, asignaturas in enlaces.items():
            self.asignaturas_enlazadas[fila_id] = list(asignaturas)
        return sum(len(a) for a in enlaces.values())


class UowFalsa:
    """Unidad de trabajo en memoria.

    `commits` cuenta las confirmaciones para poder afirmar en las pruebas que un
    caso de uso confirmo su transaccion —o que no lo hizo cuando fallo—.
    """

    def __init__(self) -> None:
        self.usuarios = RepoUsuarios()
        self.roles = RepoRoles()
        self.tokens = RepoTokens()
        self.personas = RepoPersonas()
        self.titulos = RepoTitulos()
        self.logs = RepoLogs()
        self.jobs = RepoJobs()
        self.catalogos = RepoCatalogos()
        self.docentes = RepoDocentes()
        self.distributivo = RepoDistributivo()
        self.distributivo.uow = self
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def uow() -> UowFalsa:
    return UowFalsa()


@pytest.fixture
def roles() -> dict[str, Rol]:
    return {
        codigo.value: Rol.desde_catalogo(codigo, permisos)
        for codigo, permisos in PERMISOS_POR_ROL.items()
    }


@pytest.fixture
async def uow_sembrada(uow: UowFalsa, roles: dict[str, Rol]) -> UowFalsa:
    for rol in roles.values():
        await uow.roles.agregar(rol)
    return uow


@pytest.fixture
def reloj():  # type: ignore[no-untyped-def]
    from app.domain.ports.reloj import RelojCongelado

    return RelojCongelado(MOMENTO_FIJO)


@pytest.fixture
def aleatorio():  # type: ignore[no-untyped-def]
    from app.domain.ports.reloj import AleatorioDelSistema

    # Semilla fija: los intervalos con jitter se vuelven reproducibles.
    return AleatorioDelSistema(semilla=12345)


@pytest.fixture
def hasher():  # type: ignore[no-untyped-def]
    from app.infrastructure.seguridad.hasher import HasherArgon2

    # Parametros minimos: la prueba verifica el comportamiento, no el coste.
    return HasherArgon2(memoria_kib=8, iteraciones=1, paralelismo=1)


@pytest.fixture
def tokens():  # type: ignore[no-untyped-def]
    from app.core.config import JWTSettings
    from app.infrastructure.seguridad.tokens import ServicioTokensJWT

    return ServicioTokensJWT(JWTSettings(secret_key="clave-de-prueba-" + "x" * 48))


# ---------------------------------------------------------------------------
# Constructores de datos
# ---------------------------------------------------------------------------

#: Cedulas con digito verificador correcto, para no depender del azar.
CEDULAS_VALIDAS = (
    "1710034065",
    "1713175477",
    "0926687856",
    "1104537772",
    "1802345676",
)


def hacer_persona(
    cedula: str = CEDULAS_VALIDAS[0],
    *,
    nombres: str = "Ana Maria",
    apellidos: str = "Yepez Cordova",
    activo: bool = True,
    **extra: Any,
) -> Persona:
    return Persona(
        cedula=Cedula(cedula),
        nombre=NombrePersona(nombres=nombres, apellidos=apellidos),
        activo=activo,
        **extra,
    )


def hacer_usuario(
    *,
    email: str = "usuario@ute.edu.ec",
    roles: set[Rol] | None = None,
    superusuario: bool = False,
    activo: bool = True,
    hash_contrasena: str | None = "hash",
    proveedor: AuthProvider = AuthProvider.LOCAL,
) -> Usuario:
    return Usuario(
        email=Email(email),
        nombre_completo="Usuario de Prueba",
        roles=roles or set(),
        es_superusuario=superusuario,
        activo=activo,
        hash_contrasena=hash_contrasena,
        proveedor=proveedor,
    )


def hacer_titulo(
    persona_id: UUID,
    *,
    denominacion: str = "INGENIERO EN SISTEMAS",
    institucion: str = "UNIVERSIDAD TECNOLOGICA EQUINOCCIAL",
    numero_registro: str | None = "1234-2015-567890",
    **extra: Any,
) -> Titulo:
    return Titulo(
        persona_id=persona_id,
        denominacion=denominacion,
        institucion=institucion,
        numero_registro=numero_registro,
        **extra,
    )
