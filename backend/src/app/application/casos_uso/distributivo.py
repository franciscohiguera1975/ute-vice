"""Casos de uso del distributivo docente."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import FilaDistributivo, separar_asignaturas
from app.domain.enums import Permiso
from app.domain.errors import ErrorValidacion, FueraDeAlcance, NoEncontrado, YaExiste
from app.domain.ports.distributivo import (
    FilaDistributivoResuelta,
    FiltroDistributivo,
    ResumenDistributivo,
)
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects_distributivo import DistribucionHoras


@dataclass(frozen=True, slots=True)
class EntradaListarDistributivo:
    filtro: FiltroDistributivo = field(default_factory=FiltroDistributivo)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class EntradaCrearFila:
    docente_id: UUID
    pao_id: UUID
    facultad_id: UUID
    carrera_id: UUID
    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None
    asignaturas_ids: list[UUID] = field(default_factory=list)
    horas: dict[str, float] = field(default_factory=dict)
    medida: str | None = None
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaActualizarFila:
    fila_id: UUID
    facultad_id: UUID | None = None
    carrera_id: UUID | None = None
    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None
    asignaturas_ids: list[UUID] | None = None
    horas: dict[str, float] | None = None
    medida: str | None = None
    observaciones: str | None = None


#: Catalogos obligatorios de una fila y el campo que los referencia.
_REFERENCIAS_OBLIGATORIAS: tuple[tuple[str, TipoCatalogo], ...] = (
    ("pao_id", TipoCatalogo.PAO),
    ("facultad_id", TipoCatalogo.FACULTAD),
    ("carrera_id", TipoCatalogo.CARRERA),
)

#: Catalogos opcionales. Se validan igual cuando vienen informados: una clave
#: foranea invalida se detecta aqui con un mensaje util, no como un error de
#: integridad de PostgreSQL a mitad de la transaccion.
_REFERENCIAS_OPCIONALES: tuple[tuple[str, TipoCatalogo], ...] = (
    ("sede_id", TipoCatalogo.SEDE),
    ("nivel_id", TipoCatalogo.NIVEL),
    ("titularidad_id", TipoCatalogo.TITULARIDAD),
    ("dedicacion_id", TipoCatalogo.DEDICACION),
    ("categoria_id", TipoCatalogo.CATEGORIA),
    ("tipo_titulo_id", TipoCatalogo.TIPO_TITULO),
)


class _ValidadorReferencias:
    """Comprueba que los catalogos citados por una fila existan."""

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def validar(self, entrada: object, *, obligatorias: bool) -> None:
        pares = _REFERENCIAS_OPCIONALES + (_REFERENCIAS_OBLIGATORIAS if obligatorias else ())
        for campo, tipo in pares:
            valor = getattr(entrada, campo, None)
            if valor is None:
                continue
            if (await self._uow.catalogos.obtener(tipo, valor)) is None:
                raise NoEncontrado(tipo.singular, valor)


def _construir_horas(plano: dict[str, float]) -> DistribucionHoras:
    """Valida y arma la distribucion desde el diccionario plano de la peticion."""
    validas = set(
        DistribucionHoras.CLAVES_DOCENCIA
        + DistribucionHoras.CLAVES_GESTION
        + DistribucionHoras.CLAVES_INVESTIGACION
        + DistribucionHoras.CLAVES_VINCULACION
    )
    desconocidas = sorted(set(plano) - validas)
    if desconocidas:
        raise ErrorValidacion(
            f"Claves de horas desconocidas: {', '.join(desconocidas)}", campo="horas"
        )
    negativas = sorted(k for k, v in plano.items() if v is not None and v < 0)
    if negativas:
        raise ErrorValidacion(
            f"Las horas no pueden ser negativas: {', '.join(negativas)}", campo="horas"
        )
    return DistribucionHoras.desde_plano(dict(plano))


# ---------------------------------------------------------------------------


def _asegurar_en_alcance(
    contexto: ContextoEjecucion,
    *,
    facultad_id: UUID | None,
    carrera_id: UUID | None,
    recurso: str = "registro",
) -> None:
    """Corta si la fila cae fuera de lo que el actor puede consultar.

    Los listados ya vienen recortados por la consulta, pero llegar por el
    identificador los esquiva: sin esta comprobacion, quien tuviera un `id`
    podria leer o modificar una fila de otra facultad.
    """
    if not contexto.alcance.permite(facultad_id=facultad_id, carrera_id=carrera_id):
        raise FueraDeAlcance(recurso)


class ListarDistributivo(CasoDeUso[EntradaListarDistributivo, Pagina[FilaDistributivoResuelta]]):
    """Lista filas del distributivo con sus catalogos ya resueltos a texto."""

    nombre = "distributivo.listar"
    descripcion = "Lista las filas del distributivo docente"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarDistributivo, contexto: ContextoEjecucion
    ) -> Pagina[FilaDistributivoResuelta]:
        # El alcance se impone aqui, sobre lo que haya pedido la peticion: es
        # un recorte de seguridad y no un filtro que el cliente pueda relajar.
        filtro = replace(entrada.filtro, alcance=contexto.alcance)
        async with self._uow:
            return await self._uow.distributivo.listar(filtro, entrada.paginacion)


class ObtenerFilaDistributivo(CasoDeUso[UUID, FilaDistributivoResuelta]):
    nombre = "distributivo.obtener"
    descripcion = "Obtiene una fila del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: UUID, contexto: ContextoEjecucion
    ) -> FilaDistributivoResuelta:
        async with self._uow:
            fila = await self._uow.distributivo.obtener_resuelta(entrada)
            if fila is None:
                raise NoEncontrado("Fila de distributivo", entrada)
            _asegurar_en_alcance(
                contexto,
                facultad_id=fila.fila.facultad_id,
                carrera_id=fila.fila.carrera_id,
                recurso="registro del distributivo",
            )
            return fila


class ResumenDelDistributivo(CasoDeUso[FiltroDistributivo, ResumenDistributivo]):
    """Contadores del conjunto filtrado, para la cabecera y el tablero."""

    nombre = "distributivo.resumen"
    descripcion = "Totales y distribucion del distributivo filtrado"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: FiltroDistributivo, contexto: ContextoEjecucion
    ) -> ResumenDistributivo:
        async with self._uow:
            return await self._uow.distributivo.resumen(replace(entrada, alcance=contexto.alcance))


class CrearFilaDistributivo(CasoDeUso[EntradaCrearFila, FilaDistributivo]):
    """Registra una fila del distributivo."""

    nombre = "distributivo.crear"
    descripcion = "Registra una carga docente en una carrera y periodo"
    permiso_requerido = Permiso.DISTRIBUTIVO_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaCrearFila, contexto: ContextoEjecucion
    ) -> FilaDistributivo:
        horas = _construir_horas(entrada.horas)

        _asegurar_en_alcance(
            contexto,
            facultad_id=entrada.facultad_id,
            carrera_id=entrada.carrera_id,
            recurso="registro del distributivo",
        )

        async with self._uow:
            if (await self._uow.docentes.obtener(entrada.docente_id)) is None:
                raise NoEncontrado("Docente", entrada.docente_id)

            await _ValidadorReferencias(self._uow).validar(entrada, obligatorias=True)

            if await self._uow.distributivo.existe_combinacion(
                docente_id=entrada.docente_id,
                pao_id=entrada.pao_id,
                carrera_id=entrada.carrera_id,
                sede_id=entrada.sede_id,
            ):
                raise YaExiste(
                    "fila de distributivo",
                    "docente/periodo/carrera/sede",
                    f"{entrada.docente_id}",
                )

            fila = FilaDistributivo(
                docente_id=entrada.docente_id,
                pao_id=entrada.pao_id,
                facultad_id=entrada.facultad_id,
                carrera_id=entrada.carrera_id,
                sede_id=entrada.sede_id,
                nivel_id=entrada.nivel_id,
                titularidad_id=entrada.titularidad_id,
                dedicacion_id=entrada.dedicacion_id,
                categoria_id=entrada.categoria_id,
                tipo_titulo_id=entrada.tipo_titulo_id,
                asignaturas_ids=list(entrada.asignaturas_ids),
                horas=horas,
                medida=entrada.medida,
                observaciones=entrada.observaciones,
                creado_por=contexto.actor_id,
            )
            creada = await self._uow.distributivo.agregar(fila)
            await self._uow.commit()
            return creada


class ActualizarFilaDistributivo(CasoDeUso[EntradaActualizarFila, FilaDistributivo]):
    """Modifica una fila del distributivo.

    `docente_id` y `pao_id` no se cambian: junto con la carrera son la identidad
    de la fila. Reasignar una carga a otro docente es crear una fila nueva y
    eliminar esta, no editarla.
    """

    nombre = "distributivo.actualizar"
    descripcion = "Modifica una fila del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarFila, contexto: ContextoEjecucion
    ) -> FilaDistributivo:
        horas = _construir_horas(entrada.horas) if entrada.horas is not None else None

        async with self._uow:
            fila = await self._uow.distributivo.obtener(entrada.fila_id)
            if fila is None:
                raise NoEncontrado("Fila de distributivo", entrada.fila_id)

            # Antes y despues: mover una fila fuera del propio alcance seria
            # perderla de vista, y traerla desde fuera, apropiarsela.
            _asegurar_en_alcance(
                contexto,
                facultad_id=fila.facultad_id,
                carrera_id=fila.carrera_id,
                recurso="registro del distributivo",
            )
            _asegurar_en_alcance(
                contexto,
                facultad_id=entrada.facultad_id or fila.facultad_id,
                carrera_id=entrada.carrera_id or fila.carrera_id,
                recurso="registro del distributivo",
            )

            await _ValidadorReferencias(self._uow).validar(entrada, obligatorias=False)
            if entrada.carrera_id is not None:
                await self._validar_carrera(entrada, fila)

            fila.actualizar(
                facultad_id=entrada.facultad_id,
                carrera_id=entrada.carrera_id,
                sede_id=entrada.sede_id,
                nivel_id=entrada.nivel_id,
                titularidad_id=entrada.titularidad_id,
                dedicacion_id=entrada.dedicacion_id,
                categoria_id=entrada.categoria_id,
                tipo_titulo_id=entrada.tipo_titulo_id,
                asignaturas_ids=entrada.asignaturas_ids,
                horas=horas,
                medida=entrada.medida,
                observaciones=entrada.observaciones,
            )
            actualizada = await self._uow.distributivo.actualizar(fila)
            await self._uow.commit()
            return actualizada

    async def _validar_carrera(
        self, entrada: EntradaActualizarFila, fila: FilaDistributivo
    ) -> None:
        if (
            await self._uow.catalogos.obtener(
                TipoCatalogo.CARRERA,
                entrada.carrera_id,  # type: ignore[arg-type]
            )
        ) is None:
            raise NoEncontrado("carrera", entrada.carrera_id)

        # Cambiar de carrera puede chocar con otra fila del mismo docente y
        # periodo, que es justo lo que la clave natural impide.
        if await self._uow.distributivo.existe_combinacion(
            docente_id=fila.docente_id,
            pao_id=fila.pao_id,
            carrera_id=entrada.carrera_id,  # type: ignore[arg-type]
            sede_id=entrada.sede_id if entrada.sede_id is not None else fila.sede_id,
            excluyendo=fila.id,
        ):
            raise YaExiste(
                "fila de distributivo",
                "docente/periodo/carrera/sede",
                str(entrada.carrera_id),
            )


class EliminarFilaDistributivo(CasoDeUso[UUID, None]):
    nombre = "distributivo.eliminar"
    descripcion = "Elimina una fila del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_ELIMINAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            fila = await self._uow.distributivo.obtener(entrada)
            if fila is None:
                raise NoEncontrado("Fila de distributivo", entrada)
            _asegurar_en_alcance(
                contexto,
                facultad_id=fila.facultad_id,
                carrera_id=fila.carrera_id,
                recurso="registro del distributivo",
            )
            await self._uow.distributivo.eliminar(entrada)
            await self._uow.commit()


# ===========================================================================
# Captura de asignaturas
# ===========================================================================


@dataclass(frozen=True, slots=True)
class AsignaturaDeFila:
    """Lo que se captura para una fila."""

    fila_id: UUID
    asignatura: str
    """Vacio borra la asignatura registrada."""


@dataclass(frozen=True, slots=True)
class ResultadoCapturaAsignaturas:
    actualizadas: int = 0
    sin_cambios: int = 0
    #: Asignaturas que no estaban en el catalogo y se agregaron al vuelo.
    asignaturas_creadas: int = 0


class CapturarAsignaturas(CasoDeUso[list[AsignaturaDeFila], ResultadoCapturaAsignaturas]):
    """Registra la asignatura de varias filas de una vez.

    La asignatura es el unico dato del reporte institucional que no existe en el
    consolidado —el distributivo reparte horas por tipo de actividad, no por
    materia— asi que hay que capturarla a mano para cientos de filas. Hacerlo
    con una peticion por fila convierte la tarea en algo impracticable.

    Toda la tanda va en una transaccion: o se guarda entera o no se guarda nada.
    Quien captura cincuenta filas no tiene por que averiguar cuales quedaron.
    """

    nombre = "distributivo.capturar_asignaturas"
    descripcion = "Registra la asignatura que imparte en varias filas"
    permiso_requerido = Permiso.DISTRIBUTIVO_ESCRIBIR

    #: Tope por peticion. Es una pantalla de captura, no una importacion.
    MAXIMO = 500

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow
        self._creadas: set[UUID] = set()

    async def _ejecutar(
        self, entrada: list[AsignaturaDeFila], contexto: ContextoEjecucion
    ) -> ResultadoCapturaAsignaturas:
        if not entrada:
            raise ErrorValidacion("No se recibio ninguna fila", campo="filas")
        if len(entrada) > self.MAXIMO:
            raise ErrorValidacion(
                f"No se pueden actualizar mas de {self.MAXIMO} filas por peticion; "
                f"se recibieron {len(entrada)}.",
                campo="filas",
            )

        actualizadas = 0
        sin_cambios = 0

        async with self._uow:
            for item in entrada:
                fila = await self._uow.distributivo.obtener(item.fila_id)
                if fila is not None:
                    _asegurar_en_alcance(
                        contexto,
                        facultad_id=fila.facultad_id,
                        carrera_id=fila.carrera_id,
                        recurso="registro del distributivo",
                    )
                if fila is None:
                    # Una fila inexistente aborta la tanda entera: significa que
                    # la pantalla trabaja sobre datos que ya cambiaron, y guardar
                    # el resto dejaria al usuario sin saber que quedo afuera.
                    raise NoEncontrado("Fila de distributivo", item.fila_id)

                # La pantalla manda texto, no identificadores: capturar
                # cientos de filas obligando a elegir de una lista que empieza
                # vacia no seria capturar nada. El texto se resuelve contra el
                # catalogo y, si no existe, se agrega.
                asignaturas_ids = await self._resolver(item.asignatura)
                if asignaturas_ids == fila.asignaturas_ids:
                    sin_cambios += 1
                    continue

                fila.definir_asignaturas(asignaturas_ids)
                await self._uow.distributivo.actualizar(fila)
                actualizadas += 1

            await self._uow.commit()

        return ResultadoCapturaAsignaturas(
            actualizadas=actualizadas,
            sin_cambios=sin_cambios,
            asignaturas_creadas=len(self._creadas),
        )

    async def _resolver(self, texto: str) -> list[UUID]:
        """«Calculo I, Algebra» → los elementos del catalogo. Vacio las retira.

        Busca por codigo, que es el texto en mayusculas: asi «Calculo I» y
        «CALCULO I» son la misma asignatura y no dos entradas distintas.
        """
        ids: list[UUID] = []
        for nombre in separar_asignaturas(texto):
            codigo = nombre.upper()
            existente = await self._uow.catalogos.obtener_por_codigo(
                TipoCatalogo.ASIGNATURA, codigo
            )
            if existente is not None:
                ids.append(existente.id)
                continue

            creada = await self._uow.catalogos.agregar(
                ElementoCatalogo(tipo=TipoCatalogo.ASIGNATURA, codigo=codigo, nombre=nombre)
            )
            self._creadas.add(creada.id)
            ids.append(creada.id)
        return ids
