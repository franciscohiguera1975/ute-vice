"""Repositorios del distributivo docente sobre PostgreSQL."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Integer, Select, cast, delete, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente, FilaDistributivo
from app.domain.ports.distributivo import (
    FilaDistributivoResuelta,
    FilaReporteDocencia,
    FiltroCatalogo,
    FiltroDistributivo,
    FiltroDocentes,
    ResumenDistributivo,
)
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.value_objects import normalizar_texto
from app.infrastructure.db import mapeadores_distributivo as m
from app.infrastructure.db.modelos_distributivo import (
    MODELOS_CATALOGO,
    AsignaturaModel,
    CarreraModel,
    CategoriaModel,
    DedicacionModel,
    DocenteModel,
    FacultadModel,
    FilaDistributivoModel,
    GeneroModel,
    NivelModel,
    PaoModel,
    SedeModel,
    TipoTituloModel,
    TitularidadModel,
    TituloProfesionalModel,
    distributivo_asignaturas,
    docente_titulos,
)

#: Columnas por las que se admite ordenar. Lista blanca: el `ORDER BY` nunca se
#: construye con texto que venga de la peticion.
_ORDEN_DISTRIBUTIVO: dict[str, Any] = {
    "docente": DocenteModel.nombre_completo,
    "pao": PaoModel.orden,
    "facultad": FacultadModel.codigo,
    "carrera": CarreraModel.nombre,
    "total_horas": FilaDistributivoModel.total_horas,
    "creado_en": FilaDistributivoModel.creado_en,
}


#: Codigos de catalogo que pide la exportacion en formato de origen, y el campo
#: de `FilaDistributivoResuelta` al que va cada uno. El orden importa: es el que
#: `add_columns` respeta al anadirlos a la consulta.
_CODIGOS_ORIGEN: tuple[Any, ...] = (
    CarreraModel.codigo,
    SedeModel.codigo,
    NivelModel.codigo,
    TitularidadModel.codigo,
    DedicacionModel.codigo,
    CategoriaModel.codigo,
    TipoTituloModel.codigo,
    GeneroModel.codigo,
)

_NOMBRES_CODIGOS_ORIGEN: tuple[str, ...] = (
    "codigo_carrera",
    "codigo_sede",
    "codigo_nivel",
    "codigo_titularidad",
    "codigo_dedicacion",
    "codigo_categoria",
    "codigo_tipo_titulo",
    "codigo_genero",
)


def _ids_de_asignaturas() -> Any:
    """Identificadores de las asignaturas de la fila, en su orden.

    Van ademas de los nombres porque la entidad los necesita: sin ellos,
    `requiere_asignatura` diria que falta la materia en una fila que si la
    tiene, y guardar esa entidad borraria los enlaces.
    """
    return (
        select(
            func.array_agg(
                aggregate_order_by(
                    distributivo_asignaturas.c.asignatura_id,
                    distributivo_asignaturas.c.orden,
                )
            )
        )
        .select_from(distributivo_asignaturas)
        .where(distributivo_asignaturas.c.fila_id == FilaDistributivoModel.id)
        .correlate(FilaDistributivoModel)
        .scalar_subquery()
    )


def _asignaturas_de_la_fila() -> Any:
    """Asignaturas de una fila como arreglo, en el orden en que se escribieron.

    Subconsulta correlacionada y no `JOIN`: una fila con tres materias
    multiplicaria por tres las filas del distributivo y habria que reagruparlas
    despues.
    """
    return (
        select(
            func.array_agg(
                aggregate_order_by(AsignaturaModel.nombre, distributivo_asignaturas.c.orden)
            )
        )
        .select_from(distributivo_asignaturas)
        .join(AsignaturaModel, AsignaturaModel.id == distributivo_asignaturas.c.asignatura_id)
        .where(distributivo_asignaturas.c.fila_id == FilaDistributivoModel.id)
        .correlate(FilaDistributivoModel)
        .scalar_subquery()
    )


def _titulos_del_docente() -> Any:
    """Titulos del docente como arreglo, en el orden en que los trajo el origen.

    Va como subconsulta correlacionada y no como `JOIN`: un docente con cuatro
    titulos multiplicaria por cuatro las filas del distributivo, y despues
    habria que volver a agruparlas.
    """
    return (
        select(
            func.array_agg(
                aggregate_order_by(TituloProfesionalModel.nombre, docente_titulos.c.orden)
            )
        )
        .select_from(docente_titulos)
        .join(TituloProfesionalModel, TituloProfesionalModel.id == docente_titulos.c.titulo_id)
        .where(docente_titulos.c.docente_id == DocenteModel.id)
        .correlate(DocenteModel)
        .scalar_subquery()
    )


# ===========================================================================
class RepositorioCatalogosSQL:
    """Un solo repositorio para los doce catalogos.

    El `tipo` selecciona la tabla a traves de `MODELOS_CATALOGO`. Es lo que
    permite que los doce CRUD sean el mismo codigo sin renunciar a tener una
    tabla y una clave foranea real por catalogo.
    """

    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    @staticmethod
    def _modelo(tipo: TipoCatalogo) -> Any:
        return MODELOS_CATALOGO[tipo]

    async def obtener(self, tipo: TipoCatalogo, elemento_id: UUID) -> ElementoCatalogo | None:
        fila = await self._s.get(self._modelo(tipo), elemento_id)
        return m.catalogo_a_dominio(fila, tipo) if fila else None

    async def obtener_por_codigo(self, tipo: TipoCatalogo, codigo: str) -> ElementoCatalogo | None:
        modelo = self._modelo(tipo)
        fila = await self._s.scalar(
            select(modelo).where(modelo.codigo == " ".join((codigo or "").split()).upper())
        )
        return m.catalogo_a_dominio(fila, tipo) if fila else None

    def _filtrar(self, consulta: Select[Any], modelo: Any, filtro: FiltroCatalogo) -> Select[Any]:
        if filtro.texto:
            patron = f"%{normalizar_texto(filtro.texto)}%"
            consulta = consulta.where(modelo.clave_busqueda.like(patron))
        if filtro.activo is not None:
            consulta = consulta.where(modelo.activo == filtro.activo)
        return consulta

    async def listar(
        self, tipo: TipoCatalogo, filtro: FiltroCatalogo, paginacion: Paginacion
    ) -> Pagina[ElementoCatalogo]:
        modelo = self._modelo(tipo)
        base = self._filtrar(select(modelo), modelo, filtro)
        total = (
            await self._s.scalar(
                self._filtrar(select(func.count()).select_from(modelo), modelo, filtro)
            )
        ) or 0

        columna = modelo.orden if paginacion.ordenar_por == "orden" else modelo.nombre
        if paginacion.ordenar_por == "codigo":
            columna = modelo.codigo
        base = base.order_by(columna.desc() if paginacion.descendente else columna.asc())

        filas = await self._s.scalars(base.offset(paginacion.offset).limit(paginacion.limite))
        return Pagina(
            items=[m.catalogo_a_dominio(f, tipo) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def listar_todos(
        self, tipo: TipoCatalogo, *, solo_activos: bool = True
    ) -> list[ElementoCatalogo]:
        modelo = self._modelo(tipo)
        consulta = select(modelo)
        if solo_activos:
            consulta = consulta.where(modelo.activo.is_(True))
        # Orden explicito primero, alfabetico despues: los catalogos con
        # secuencia natural (PAO) la respetan y el resto sale legible.
        filas = await self._s.scalars(consulta.order_by(modelo.orden, modelo.nombre))
        return [m.catalogo_a_dominio(f, tipo) for f in filas]

    async def agregar(self, elemento: ElementoCatalogo) -> ElementoCatalogo:
        self._s.add(m.catalogo_a_modelo(elemento))
        await self._s.flush()
        return elemento

    async def agregar_muchos(self, elementos: list[ElementoCatalogo]) -> int:
        if not elementos:
            return 0
        self._s.add_all([m.catalogo_a_modelo(e) for e in elementos])
        await self._s.flush()
        return len(elementos)

    async def actualizar(self, elemento: ElementoCatalogo) -> ElementoCatalogo:
        modelo = await self._s.get(self._modelo(elemento.tipo), elemento.id)
        if modelo is None:
            raise ValueError(f"Elemento de catalogo inexistente: {elemento.id}")
        m.catalogo_a_modelo(elemento, modelo)
        await self._s.flush()
        return elemento

    async def eliminar(self, tipo: TipoCatalogo, elemento_id: UUID) -> None:
        modelo = self._modelo(tipo)
        await self._s.execute(delete(modelo).where(modelo.id == elemento_id))

    async def existe_codigo(
        self, tipo: TipoCatalogo, codigo: str, *, excluyendo: UUID | None = None
    ) -> bool:
        modelo = self._modelo(tipo)
        consulta = (
            select(func.count())
            .select_from(modelo)
            .where(modelo.codigo == " ".join((codigo or "").split()).upper())
        )
        if excluyendo:
            consulta = consulta.where(modelo.id != excluyendo)
        return bool(await self._s.scalar(consulta))

    async def contar_referencias(self, tipo: TipoCatalogo, elemento_id: UUID) -> int:
        """Cuantas filas del distributivo apuntan a este elemento."""
        columna = {
            TipoCatalogo.PAO: FilaDistributivoModel.pao_id,
            TipoCatalogo.FACULTAD: FilaDistributivoModel.facultad_id,
            TipoCatalogo.CARRERA: FilaDistributivoModel.carrera_id,
            TipoCatalogo.SEDE: FilaDistributivoModel.sede_id,
            TipoCatalogo.NIVEL: FilaDistributivoModel.nivel_id,
            TipoCatalogo.TITULARIDAD: FilaDistributivoModel.titularidad_id,
            TipoCatalogo.DEDICACION: FilaDistributivoModel.dedicacion_id,
            TipoCatalogo.CATEGORIA: FilaDistributivoModel.categoria_id,
            TipoCatalogo.TIPO_TITULO: FilaDistributivoModel.tipo_titulo_id,
        }.get(tipo)

        if columna is not None:
            return (
                await self._s.scalar(
                    select(func.count())
                    .select_from(FilaDistributivoModel)
                    .where(columna == elemento_id)
                )
            ) or 0

        if tipo is TipoCatalogo.GENERO:
            return (
                await self._s.scalar(
                    select(func.count())
                    .select_from(DocenteModel)
                    .where(DocenteModel.genero_id == elemento_id)
                )
            ) or 0

        if tipo is TipoCatalogo.TITULO_PROFESIONAL:
            return (
                await self._s.scalar(
                    select(func.count())
                    .select_from(docente_titulos)
                    .where(docente_titulos.c.titulo_id == elemento_id)
                )
            ) or 0

        return 0


# ===========================================================================
class RepositorioDocentesSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener(self, docente_id: UUID) -> Docente | None:
        fila = await self._s.get(DocenteModel, docente_id)
        return m.docente_a_dominio(fila) if fila else None

    async def obtener_por_identificacion(self, identificacion: str) -> Docente | None:
        fila = await self._s.scalar(
            select(DocenteModel).where(
                DocenteModel.identificacion == identificacion.strip().upper()
            )
        )
        return m.docente_a_dominio(fila) if fila else None

    def _filtrar(self, consulta: Select[Any], filtro: FiltroDocentes) -> Select[Any]:
        if filtro.texto:
            consulta = consulta.where(
                DocenteModel.clave_busqueda.like(f"%{normalizar_texto(filtro.texto)}%")
            )
        if filtro.identificacion:
            consulta = consulta.where(
                DocenteModel.identificacion == filtro.identificacion.strip().upper()
            )
        if filtro.genero_id:
            consulta = consulta.where(DocenteModel.genero_id == filtro.genero_id)
        if filtro.activo is not None:
            consulta = consulta.where(DocenteModel.activo == filtro.activo)
        if filtro.solo_con_pasaporte:
            consulta = consulta.where(DocenteModel.es_cedula.is_(False))
        if filtro.vinculado_a_persona is not None:
            consulta = consulta.where(
                DocenteModel.persona_id.isnot(None)
                if filtro.vinculado_a_persona
                else DocenteModel.persona_id.is_(None)
            )
        return consulta

    async def listar(self, filtro: FiltroDocentes, paginacion: Paginacion) -> Pagina[Docente]:
        base = self._filtrar(select(DocenteModel), filtro)
        total = (
            await self._s.scalar(
                self._filtrar(select(func.count()).select_from(DocenteModel), filtro)
            )
        ) or 0
        filas = await self._s.scalars(
            base.order_by(DocenteModel.nombre_completo)
            .offset(paginacion.offset)
            .limit(paginacion.limite)
        )
        return Pagina(
            items=[m.docente_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def agregar(self, docente: Docente) -> Docente:
        modelo = m.docente_a_modelo(docente)
        modelo.titulos = await self._modelos_titulos(docente.titulos_ids)
        self._s.add(modelo)
        await self._s.flush()
        return docente

    async def agregar_muchos(self, docentes: list[Docente]) -> int:
        if not docentes:
            return 0
        for docente in docentes:
            modelo = m.docente_a_modelo(docente)
            modelo.titulos = await self._modelos_titulos(docente.titulos_ids)
            self._s.add(modelo)
        await self._s.flush()
        return len(docentes)

    async def actualizar(self, docente: Docente) -> Docente:
        modelo = await self._s.get(DocenteModel, docente.id)
        if modelo is None:
            raise ValueError(f"Docente inexistente: {docente.id}")
        m.docente_a_modelo(docente, modelo)
        modelo.titulos = await self._modelos_titulos(docente.titulos_ids)
        await self._s.flush()
        return docente

    async def eliminar(self, docente_id: UUID) -> None:
        await self._s.execute(delete(DocenteModel).where(DocenteModel.id == docente_id))

    async def existe_identificacion(
        self, identificacion: str, *, excluyendo: UUID | None = None
    ) -> bool:
        consulta = (
            select(func.count())
            .select_from(DocenteModel)
            .where(DocenteModel.identificacion == identificacion.strip().upper())
        )
        if excluyendo:
            consulta = consulta.where(DocenteModel.id != excluyendo)
        return bool(await self._s.scalar(consulta))

    async def contar_filas(self, docente_id: UUID) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(FilaDistributivoModel)
                .where(FilaDistributivoModel.docente_id == docente_id)
            )
        ) or 0

    async def titulos_de(self, docente_id: UUID) -> list[ElementoCatalogo]:
        filas = await self._s.scalars(
            select(TituloProfesionalModel)
            .join(
                docente_titulos,
                docente_titulos.c.titulo_id == TituloProfesionalModel.id,
            )
            .where(docente_titulos.c.docente_id == docente_id)
            .order_by(docente_titulos.c.orden)
        )
        return [m.catalogo_a_dominio(f, TipoCatalogo.TITULO_PROFESIONAL) for f in filas]

    async def _modelos_titulos(self, titulos_ids: list[UUID]) -> list[TituloProfesionalModel]:
        if not titulos_ids:
            return []
        filas = await self._s.scalars(
            select(TituloProfesionalModel).where(TituloProfesionalModel.id.in_(titulos_ids))
        )
        por_id = {f.id: f for f in filas}
        return [por_id[i] for i in titulos_ids if i in por_id]


# ===========================================================================
class RepositorioDistributivoSQL:
    """Filas del distributivo, con sus catalogos resueltos en una sola consulta."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    # ------------------------------------------------------- consulta base
    def _consulta_resuelta(self) -> Select[Any]:
        """Fila unida a todos sus catalogos.

        Se resuelven aqui y no con carga diferida: pintar cien filas del listado
        dispararia mil consultas, una por cada catalogo de cada fila.
        """
        return (
            select(
                FilaDistributivoModel,
                DocenteModel.identificacion,
                DocenteModel.nombre_completo,
                PaoModel.nombre,
                PaoModel.atributos["semestre"].astext,
                FacultadModel.codigo,
                CarreraModel.nombre,
                SedeModel.nombre,
                NivelModel.nombre,
                TitularidadModel.nombre,
                DedicacionModel.nombre,
                CategoriaModel.nombre,
                TipoTituloModel.nombre,
                GeneroModel.nombre,
                _asignaturas_de_la_fila(),
                _ids_de_asignaturas(),
                _titulos_del_docente(),
            )
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id)
            .join(PaoModel, PaoModel.id == FilaDistributivoModel.pao_id)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .join(CarreraModel, CarreraModel.id == FilaDistributivoModel.carrera_id)
            .outerjoin(SedeModel, SedeModel.id == FilaDistributivoModel.sede_id)
            .outerjoin(NivelModel, NivelModel.id == FilaDistributivoModel.nivel_id)
            .outerjoin(
                TitularidadModel, TitularidadModel.id == FilaDistributivoModel.titularidad_id
            )
            .outerjoin(DedicacionModel, DedicacionModel.id == FilaDistributivoModel.dedicacion_id)
            .outerjoin(CategoriaModel, CategoriaModel.id == FilaDistributivoModel.categoria_id)
            .outerjoin(TipoTituloModel, TipoTituloModel.id == FilaDistributivoModel.tipo_titulo_id)
            .outerjoin(GeneroModel, GeneroModel.id == DocenteModel.genero_id)
        )

    def _filtrar(self, consulta: Select[Any], filtro: FiltroDistributivo) -> Select[Any]:
        f = FilaDistributivoModel
        if filtro.texto:
            consulta = consulta.where(
                DocenteModel.clave_busqueda.like(f"%{normalizar_texto(filtro.texto)}%")
            )
        if filtro.docente_id:
            consulta = consulta.where(f.docente_id == filtro.docente_id)
        if filtro.pao_id:
            consulta = consulta.where(f.pao_id == filtro.pao_id)
        if filtro.pao_ids:
            consulta = consulta.where(f.pao_id.in_(filtro.pao_ids))
        if filtro.facultad_id:
            consulta = consulta.where(f.facultad_id == filtro.facultad_id)
        if filtro.facultad_ids:
            consulta = consulta.where(f.facultad_id.in_(filtro.facultad_ids))
        if filtro.carrera_id:
            consulta = consulta.where(f.carrera_id == filtro.carrera_id)
        if filtro.carrera_ids:
            # Varias carreras a la vez: es como se emite el reporte institucional.
            consulta = consulta.where(f.carrera_id.in_(filtro.carrera_ids))
        if filtro.sede_id:
            consulta = consulta.where(f.sede_id == filtro.sede_id)
        if filtro.nivel_id:
            consulta = consulta.where(f.nivel_id == filtro.nivel_id)
        if filtro.titularidad_id:
            consulta = consulta.where(f.titularidad_id == filtro.titularidad_id)
        if filtro.dedicacion_id:
            consulta = consulta.where(f.dedicacion_id == filtro.dedicacion_id)
        if filtro.categoria_id:
            consulta = consulta.where(f.categoria_id == filtro.categoria_id)
        if filtro.tipo_titulo_id:
            consulta = consulta.where(f.tipo_titulo_id == filtro.tipo_titulo_id)
        if filtro.sin_asignatura:
            # Filas que dictan clase pero nadie registro que asignatura: es lo
            # que queda en blanco en el reporte institucional.
            # Sin ninguna asignatura enlazada. `NOT EXISTS` y no un `LEFT JOIN`
            # con `IS NULL`: la fila puede tener varias y basta con que no
            # tenga ninguna.
            consulta = consulta.where(
                f.total_docencia > 0,
                ~select(distributivo_asignaturas.c.fila_id)
                .where(distributivo_asignaturas.c.fila_id == f.id)
                .exists(),
            )
        if filtro.con_carga is not None:
            consulta = consulta.where(f.total_horas > 0 if filtro.con_carga else f.total_horas == 0)

        # El alcance va al final y siempre: es un recorte de seguridad, no un
        # filtro mas. Se suman facultades y carreras en lugar de cruzarlas —ver
        # `domain/alcance.py`—, de ahi el `or_`.
        if filtro.alcance is not None and not filtro.alcance.es_total:
            permitido = []
            if filtro.alcance.facultades:
                permitido.append(f.facultad_id.in_(filtro.alcance.facultades))
            if filtro.alcance.carreras:
                permitido.append(f.carrera_id.in_(filtro.alcance.carreras))
            consulta = consulta.where(or_(*permitido))
        return consulta

    @staticmethod
    def _a_resuelta(fila: Any, *, con_codigos: bool = False) -> FilaDistributivoResuelta:
        entidad = m.fila_a_dominio(fila[0])
        # La entidad no las trae del modelo: viven en la tabla de union.
        entidad.asignaturas_ids = list(fila[15] or ())
        codigos: dict[str, Any] = {}
        if con_codigos:
            # Las anaden `add_columns` en `filas_resueltas`, despues de las
            # diecisiete de la consulta base y en el orden de `_CODIGOS_ORIGEN`.
            codigos = {nombre: fila[17 + i] for i, nombre in enumerate(_NOMBRES_CODIGOS_ORIGEN)}
        return FilaDistributivoResuelta(
            fila=entidad,
            docente_identificacion=fila[1],
            docente_nombre=fila[2],
            pao=fila[3],
            pao_semestre=fila[4] or "",
            facultad=fila[5],
            carrera=fila[6],
            sede=fila[7],
            nivel=fila[8],
            titularidad=fila[9],
            dedicacion=fila[10],
            categoria=fila[11],
            tipo_titulo=fila[12],
            genero=fila[13],
            asignaturas=tuple(fila[14] or ()),
            titulos=tuple(fila[16] or ()),
            **codigos,
        )

    # ------------------------------------------------------------- lectura
    async def obtener(self, fila_id: UUID) -> FilaDistributivo | None:
        modelo = await self._s.get(FilaDistributivoModel, fila_id)
        if modelo is None:
            return None

        fila = m.fila_a_dominio(modelo)
        # Las asignaturas viven en la tabla de union: sin esta consulta, la
        # entidad saldria sin ellas y guardarla las borraria.
        fila.asignaturas_ids = list(
            await self._s.scalars(
                select(distributivo_asignaturas.c.asignatura_id)
                .where(distributivo_asignaturas.c.fila_id == fila_id)
                .order_by(distributivo_asignaturas.c.orden)
            )
        )
        return fila

    async def obtener_resuelta(self, fila_id: UUID) -> FilaDistributivoResuelta | None:
        resultado = (
            await self._s.execute(
                self._consulta_resuelta().where(FilaDistributivoModel.id == fila_id)
            )
        ).first()
        return self._a_resuelta(resultado) if resultado else None

    async def listar(
        self, filtro: FiltroDistributivo, paginacion: Paginacion
    ) -> Pagina[FilaDistributivoResuelta]:
        base = self._filtrar(self._consulta_resuelta(), filtro)

        conteo = self._filtrar(
            select(func.count())
            .select_from(FilaDistributivoModel)
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id),
            filtro,
        )
        total = (await self._s.scalar(conteo)) or 0

        columna = _ORDEN_DISTRIBUTIVO.get(
            paginacion.ordenar_por or "", DocenteModel.nombre_completo
        )
        base = base.order_by(columna.desc() if paginacion.descendente else columna.asc())

        filas = (
            await self._s.execute(base.offset(paginacion.offset).limit(paginacion.limite))
        ).all()
        return Pagina(
            items=[self._a_resuelta(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    # ------------------------------------------------------------ escritura
    async def _guardar_asignaturas(self, filas: list[FilaDistributivo]) -> None:
        """Reemplaza las asignaturas enlazadas por las de las entidades.

        Se borra y se vuelve a insertar en lugar de comparar: la lista tiene
        dos o tres elementos y el orden importa, asi que reconstruirla sale mas
        barato y mas claro que averiguar que cambio.
        """
        ids = [f.id for f in filas]
        if not ids:
            return

        await self._s.execute(
            delete(distributivo_asignaturas).where(distributivo_asignaturas.c.fila_id.in_(ids))
        )
        enlaces = [
            {"fila_id": fila.id, "asignatura_id": asignatura_id, "orden": orden}
            for fila in filas
            for orden, asignatura_id in enumerate(fila.asignaturas_ids)
        ]
        if enlaces:
            await self._s.execute(distributivo_asignaturas.insert(), enlaces)

    async def agregar(self, fila: FilaDistributivo) -> FilaDistributivo:
        self._s.add(m.fila_a_modelo(fila))
        await self._s.flush()
        await self._guardar_asignaturas([fila])
        return fila

    async def agregar_muchas(self, filas: list[FilaDistributivo]) -> int:
        if not filas:
            return 0
        self._s.add_all([m.fila_a_modelo(f) for f in filas])
        await self._s.flush()
        await self._guardar_asignaturas(filas)
        return len(filas)

    async def reemplazar_muchas(self, filas: list[FilaDistributivo]) -> tuple[int, int]:
        """Inserta o actualiza segun la clave natural. Devuelve `(altas, cambios)`.

        El choque lo resuelve PostgreSQL con la restriccion que ya define la
        clave natural —docente, periodo, carrera y sede—, y no una comparacion
        escrita aqui. La diferencia importa: reproducir esa clave en Python
        obliga a repetir la normalizacion de cedulas, sedes y catalogos, y basta
        equivocarse en una para duplicar filas en lugar de actualizarlas.

        **No toca `distributivo_asignaturas`.** Al conservar el id de la fila,
        las materias enlazadas sobreviven a la recarga de un periodo; borrar e
        insertar las habria perdido.

        `xmax = 0` distingue la fila recien insertada de la actualizada: es el
        identificador de la transaccion que la bloqueo, y en una insercion
        limpia vale cero.
        """
        if not filas:
            return (0, 0)

        altas = cambios = 0

        #: Lo que se escribe. La clave natural —docente, periodo, carrera y
        #: sede— no esta aqui: es lo que identifica la fila, no lo que cambia.
        columnas = (
            "facultad_id",
            "nivel_id",
            "titularidad_id",
            "dedicacion_id",
            "categoria_id",
            "tipo_titulo_id",
            "horas_docencia",
            "horas_gestion",
            "horas_investigacion",
            "horas_vinculacion",
            "total_docencia",
            "total_gestion",
            "total_investigacion",
            "total_vinculacion",
            "total_horas",
            "medida",
            "observaciones",
            "estado_validacion",
            "fase",
            "semanas",
            "relacion_laboral",
            "tutor_posgrado",
            "tutor_medicina",
        )

        for inicio in range(0, len(filas), 500):
            # Todos los registros deben traer las MISMAS claves: en un VALUES
            # de varias filas, omitir una columna en unas y no en otras —como
            # `sede_id`, que es nula en dieciseis— no compila.
            claves = ("id", "docente_id", "pao_id", "carrera_id", "sede_id", "creado_por")
            registros = [
                {c: getattr(m.fila_a_modelo(fila), c) for c in (*claves, *columnas)}
                for fila in filas[inicio : inicio + 500]
            ]

            insercion = pg_insert(FilaDistributivoModel).values(registros)
            sentencia: Any = insercion.on_conflict_do_update(
                constraint="uq_distributivo_docente_pao_carrera_sede",
                set_={
                    **{c: getattr(insercion.excluded, c) for c in columnas},
                    # `onupdate` no se dispara en un upsert del nucleo: la marca
                    # de tiempo hay que ponerla a mano o la fila quedaria
                    # fechada como el dia que se creo.
                    "actualizado_en": func.now(),
                },
            ).returning(literal_column("(xmax = 0)").label("es_alta"))

            for (es_alta,) in (await self._s.execute(sentencia)).all():
                if es_alta:
                    altas += 1
                else:
                    cambios += 1

        return (altas, cambios)

    async def actualizar(self, fila: FilaDistributivo) -> FilaDistributivo:
        modelo = await self._s.get(FilaDistributivoModel, fila.id)
        if modelo is None:
            raise ValueError(f"Fila de distributivo inexistente: {fila.id}")
        m.fila_a_modelo(fila, modelo)
        await self._s.flush()
        await self._guardar_asignaturas([fila])
        return fila

    async def eliminar(self, fila_id: UUID) -> None:
        await self._s.execute(
            delete(FilaDistributivoModel).where(FilaDistributivoModel.id == fila_id)
        )

    async def existe_combinacion(
        self,
        *,
        docente_id: UUID,
        pao_id: UUID,
        carrera_id: UUID,
        sede_id: UUID | None = None,
        excluyendo: UUID | None = None,
    ) -> bool:
        consulta = (
            select(func.count())
            .select_from(FilaDistributivoModel)
            .where(
                FilaDistributivoModel.docente_id == docente_id,
                FilaDistributivoModel.pao_id == pao_id,
                FilaDistributivoModel.carrera_id == carrera_id,
                FilaDistributivoModel.sede_id.is_(None)
                if sede_id is None
                else FilaDistributivoModel.sede_id == sede_id,
            )
        )
        if excluyendo:
            consulta = consulta.where(FilaDistributivoModel.id != excluyendo)
        return bool(await self._s.scalar(consulta))

    # ------------------------------------------------------------- resumen
    async def resumen(self, filtro: FiltroDistributivo) -> ResumenDistributivo:
        totales = (
            await self._s.execute(
                self._filtrar(
                    select(
                        func.count().label("filas"),
                        func.count(func.distinct(FilaDistributivoModel.docente_id)).label(
                            "docentes"
                        ),
                        func.coalesce(func.sum(FilaDistributivoModel.total_horas), 0.0).label(
                            "horas"
                        ),
                        func.sum(
                            func.cast(
                                (FilaDistributivoModel.total_docencia > 0)
                                & ~select(distributivo_asignaturas.c.fila_id)
                                .where(
                                    distributivo_asignaturas.c.fila_id == FilaDistributivoModel.id
                                )
                                .exists(),
                                Integer,
                            )
                        ).label("sin_asignatura"),
                    )
                    .select_from(FilaDistributivoModel)
                    .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id),
                    filtro,
                )
            )
        ).one()

        async def agrupar(modelo: Any, columna_fk: Any) -> list[tuple[str, int]]:
            filas = (
                await self._s.execute(
                    self._filtrar(
                        select(modelo.nombre, func.count())
                        .select_from(FilaDistributivoModel)
                        .join(
                            DocenteModel,
                            DocenteModel.id == FilaDistributivoModel.docente_id,
                        )
                        .join(modelo, modelo.id == columna_fk),
                        filtro,
                    )
                    .group_by(modelo.nombre)
                    .order_by(func.count().desc())
                )
            ).all()
            return [(str(n), int(c)) for n, c in filas]

        return ResumenDistributivo(
            total_filas=int(totales.filas or 0),
            total_docentes=int(totales.docentes or 0),
            total_horas=round(float(totales.horas or 0.0), 2),
            filas_sin_asignatura=int(totales.sin_asignatura or 0),
            por_categoria=await agrupar(CategoriaModel, FilaDistributivoModel.categoria_id),
            por_dedicacion=await agrupar(DedicacionModel, FilaDistributivoModel.dedicacion_id),
            por_facultad=await agrupar(FacultadModel, FilaDistributivoModel.facultad_id),
        )

    # -------------------------------------------------------------- reporte
    async def unidades_por_docente(self) -> dict[UUID, str]:
        # `DISTINCT ON` con el orden por periodo descendente deja una fila por
        # docente: la de su periodo mas reciente. Es una sola pasada, frente a
        # una consulta por docente sobre tres mil.
        consulta = (
            select(FilaDistributivoModel.docente_id, FacultadModel.nombre)
            .distinct(FilaDistributivoModel.docente_id)
            .join(PaoModel, PaoModel.id == FilaDistributivoModel.pao_id)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .order_by(FilaDistributivoModel.docente_id, PaoModel.orden.desc())
        )
        return dict((await self._s.execute(consulta)).all())  # type: ignore[arg-type]

    async def filas_de_carreras(self, carreras_ids: list[UUID]) -> list[FilaDistributivo]:
        """Todas las filas que apuntan a alguna de esas carreras.

        Con sus asignaturas cargadas: al unificar dos filas hay que unir sus
        listas, y sin ellas guardar la resultante las borraria.
        """
        if not carreras_ids:
            return []
        consulta = select(FilaDistributivoModel).where(
            FilaDistributivoModel.carrera_id.in_(carreras_ids)
        )
        modelos = (await self._s.scalars(consulta)).all()
        if not modelos:
            return []

        enlaces = await self._s.execute(
            select(distributivo_asignaturas.c.fila_id, distributivo_asignaturas.c.asignatura_id)
            .where(distributivo_asignaturas.c.fila_id.in_([m.id for m in modelos]))
            .order_by(distributivo_asignaturas.c.fila_id, distributivo_asignaturas.c.orden)
        )
        por_fila: dict[UUID, list[UUID]] = {}
        for fila_id, asignatura_id in enlaces.all():
            por_fila.setdefault(fila_id, []).append(asignatura_id)

        filas = []
        for modelo in modelos:
            fila = m.fila_a_dominio(modelo)
            fila.asignaturas_ids = por_fila.get(modelo.id, [])
            filas.append(fila)
        return filas

    async def indice_para_materias(self) -> list[tuple[UUID, str, str]]:
        """`(fila_id, identificacion, codigo_del_periodo)` de todas las filas.

        Se devuelve plano y sin agrupar: quien importa materias necesita
        indexarlo por docente y semestre, pero esa decision es suya. Aqui solo
        se evita hacer quince mil consultas —una por fila— para lo que cabe en
        una.
        """
        consulta = (
            select(FilaDistributivoModel.id, DocenteModel.identificacion, PaoModel.codigo)
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id)
            .join(PaoModel, PaoModel.id == FilaDistributivoModel.pao_id)
        )
        return [(f[0], f[1], f[2]) for f in (await self._s.execute(consulta)).all()]

    async def enlazar_asignaturas(self, enlaces: dict[UUID, list[UUID]]) -> int:
        """Reemplaza las asignaturas de las filas indicadas.

        Reemplaza y no agrega: volver a cargar el mismo reporte tiene que dejar
        el mismo resultado, no duplicar los enlaces. Las filas que no aparecen
        en `enlaces` no se tocan.
        """
        if not enlaces:
            return 0

        ids = list(enlaces)
        # En lotes: `IN` con quince mil parametros supera el limite del
        # protocolo de PostgreSQL, que admite 65.535 por sentencia.
        for inicio in range(0, len(ids), 5_000):
            await self._s.execute(
                delete(distributivo_asignaturas).where(
                    distributivo_asignaturas.c.fila_id.in_(ids[inicio : inicio + 5_000])
                )
            )

        registros = [
            {"fila_id": fila_id, "asignatura_id": asignatura_id, "orden": orden}
            for fila_id, asignaturas in enlaces.items()
            for orden, asignatura_id in enumerate(asignaturas)
        ]
        for inicio in range(0, len(registros), 5_000):
            await self._s.execute(
                distributivo_asignaturas.insert(), registros[inicio : inicio + 5_000]
            )
        return len(registros)

    async def carreras_presentes(self, filtro: FiltroDistributivo) -> list[ElementoCatalogo]:
        consulta = (
            select(CarreraModel)
            .distinct()
            .select_from(FilaDistributivoModel)
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id)
            .join(CarreraModel, CarreraModel.id == FilaDistributivoModel.carrera_id)
            .order_by(CarreraModel.nombre)
        )
        # Se reutiliza el filtro entero —periodos, facultades y alcance— para
        # que la lista ofrecida coincida exactamente con lo que despues saldra
        # en el archivo. Ofrecer una carrera que luego devuelve cero filas es
        # peor que no ofrecerla.
        filas = await self._s.scalars(self._filtrar(consulta, filtro))
        return [m.catalogo_a_dominio(f, TipoCatalogo.CARRERA) for f in filas]

    async def facultades_presentes(self, filtro: FiltroDistributivo) -> list[ElementoCatalogo]:
        """Facultades con filas en los periodos elegidos.

        Mismo motivo que `carreras_presentes`: el catalogo tiene once
        facultades y varias dejaron de existir en la reestructuracion de
        2026-1. Ofrecerlas todas al elegir un periodo reciente lleva a marcar
        una que devuelve cero filas y a no entender por que.
        """
        consulta = (
            select(FacultadModel)
            .distinct()
            .select_from(FilaDistributivoModel)
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .order_by(FacultadModel.codigo)
        )
        filas = await self._s.scalars(self._filtrar(consulta, filtro))
        return [m.catalogo_a_dominio(f, TipoCatalogo.FACULTAD) for f in filas]

    async def filas_resueltas(self, filtro: FiltroDistributivo) -> list[FilaDistributivoResuelta]:
        # Se piden tambien los codigos —el texto con que el consolidado nombraba
        # cada catalogo— porque de aqui sale la exportacion que reproduce el
        # archivo de origen. Los listados no los necesitan y no los pagan.
        consulta = (
            self._filtrar(self._consulta_resuelta(), filtro)
            .add_columns(*_CODIGOS_ORIGEN)
            .order_by(
                PaoModel.orden,
                FacultadModel.codigo,
                CarreraModel.nombre,
                DocenteModel.nombre_completo,
            )
        )
        filas = (await self._s.execute(consulta)).all()
        return [self._a_resuelta(f, con_codigos=True) for f in filas]

    async def filas_para_reporte(self, filtro: FiltroDistributivo) -> list[FilaReporteDocencia]:
        """Arma el reporte institucional de docentes por carrera.

        Dos datos se derivan aqui porque la base los resuelve mejor que un
        recorrido en memoria:

        * **Titulo profesional**: el primero de los titulos del docente. El
          consolidado los concatena en una sola celda y el primero suele ser el
          grado base; los demas son especializaciones y posgrados, que el
          reporte pide aparte en «grado academico mas alto».
        * **Anio de inicio en la carrera**: el periodo mas antiguo en que ese
          docente aparece en esa carrera, **sobre todo el historico** y no solo
          sobre el periodo filtrado. Restringirlo al filtro devolveria siempre
          el anio consultado, que no es lo que la columna significa.
        """
        primer_titulo = (
            select(TituloProfesionalModel.nombre)
            .select_from(docente_titulos)
            .join(
                TituloProfesionalModel,
                TituloProfesionalModel.id == docente_titulos.c.titulo_id,
            )
            .where(docente_titulos.c.docente_id == DocenteModel.id)
            .order_by(docente_titulos.c.orden)
            .limit(1)
            .scalar_subquery()
        )

        # El consolidado deja `TIPOTITULO` vacio en periodos completos —todo
        # 2026-1 viene con «NA»—, y sin este respaldo la columna «grado academico
        # mas alto completado» saldria en blanco para 1.542 docentes. El grado no
        # se pierde: si en 2025-2 constaba PHD, en 2026-1 sigue siendo PHD. Se
        # toma el ultimo grado conocido del docente en cualquier periodo.
        fila_grado = aliased(FilaDistributivoModel)
        pao_grado = aliased(PaoModel)
        tipo_grado = aliased(TipoTituloModel)
        ultimo_grado = (
            select(tipo_grado.nombre)
            .select_from(fila_grado)
            .join(pao_grado, pao_grado.id == fila_grado.pao_id)
            .join(tipo_grado, tipo_grado.id == fila_grado.tipo_titulo_id)
            .where(fila_grado.docente_id == FilaDistributivoModel.docente_id)
            .order_by(pao_grado.orden.desc())
            .limit(1)
            .scalar_subquery()
        )

        historico = aliased(FilaDistributivoModel)
        pao_historico = aliased(PaoModel)
        # `orden` vale anio*10+periodo, asi que dividirlo entre 10 devuelve el
        # anio sin tener que convertir el JSONB del catalogo.
        anio_inicio = (
            select(func.min(pao_historico.orden) / 10)
            .select_from(historico)
            .join(pao_historico, pao_historico.id == historico.pao_id)
            .where(
                historico.docente_id == FilaDistributivoModel.docente_id,
                historico.carrera_id == FilaDistributivoModel.carrera_id,
            )
            .scalar_subquery()
        )

        consulta = (
            select(
                DocenteModel.nombre_completo,
                DocenteModel.identificacion,
                primer_titulo.label("titulo_profesional"),
                func.coalesce(TipoTituloModel.nombre, ultimo_grado).label("grado"),
                # Todas las materias de la fila en una sola celda, separadas por
                # comas: es lo que pide la columna «Asignatura que imparte» del
                # reporte institucional.
                func.coalesce(
                    select(
                        func.string_agg(
                            AsignaturaModel.nombre,
                            aggregate_order_by(
                                literal_column("', '"), distributivo_asignaturas.c.orden
                            ),
                        )
                    )
                    .select_from(distributivo_asignaturas)
                    .join(
                        AsignaturaModel,
                        AsignaturaModel.id == distributivo_asignaturas.c.asignatura_id,
                    )
                    .where(distributivo_asignaturas.c.fila_id == FilaDistributivoModel.id)
                    .correlate(FilaDistributivoModel)
                    .scalar_subquery(),
                    "",
                ).label("asignatura"),
                anio_inicio.label("anio_inicio"),
                CategoriaModel.nombre.label("categoria"),
                DedicacionModel.nombre.label("dedicacion"),
                TitularidadModel.nombre.label("titularidad"),
                FacultadModel.nombre.label("facultad"),
                SedeModel.nombre.label("sede"),
                cast(PaoModel.orden / 10, Integer).label("anio_actual"),
                CarreraModel.nombre.label("carrera"),
                FilaDistributivoModel.total_horas,
                FilaDistributivoModel.total_docencia,
            )
            .join(DocenteModel, DocenteModel.id == FilaDistributivoModel.docente_id)
            .join(PaoModel, PaoModel.id == FilaDistributivoModel.pao_id)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .join(CarreraModel, CarreraModel.id == FilaDistributivoModel.carrera_id)
            .outerjoin(SedeModel, SedeModel.id == FilaDistributivoModel.sede_id)
            .outerjoin(
                TitularidadModel, TitularidadModel.id == FilaDistributivoModel.titularidad_id
            )
            .outerjoin(DedicacionModel, DedicacionModel.id == FilaDistributivoModel.dedicacion_id)
            .outerjoin(CategoriaModel, CategoriaModel.id == FilaDistributivoModel.categoria_id)
            .outerjoin(TipoTituloModel, TipoTituloModel.id == FilaDistributivoModel.tipo_titulo_id)
        )
        consulta = self._filtrar(consulta, filtro).order_by(
            CarreraModel.nombre, DocenteModel.nombre_completo
        )

        filas = (await self._s.execute(consulta)).all()
        return [
            FilaReporteDocencia(
                numero=i,
                nombre=f.nombre_completo,
                titulo_profesional=f.titulo_profesional or "",
                grado_academico=f.grado or "",
                asignatura=f.asignatura or "",
                anio_inicio_carrera=int(f.anio_inicio) if f.anio_inicio else None,
                jerarquia_docente=f.categoria or "",
                dedicacion_horaria=f.dedicacion or "",
                tipo_contrato=f.titularidad or "",
                unidad=f.facultad or "",
                comuna=f.sede or "",
                anio_actual=int(f.anio_actual or 0),
                identificacion=f.identificacion,
                carrera=f.carrera or "",
                total_horas=float(f.total_horas or 0.0),
                total_docencia=float(f.total_docencia or 0.0),
            )
            for i, f in enumerate(filas, start=1)
        ]
