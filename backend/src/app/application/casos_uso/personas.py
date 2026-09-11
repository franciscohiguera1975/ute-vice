"""Casos de uso sobre personas (empleados de la institucion)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import Permiso, TipoVinculacion
from app.domain.errors import ErrorValidacion, NoEncontrado, ReglaDeNegocioViolada, YaExiste
from app.domain.ports.repositorios import FiltroPersonas, Pagina, Paginacion
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import Cedula, Email, NombrePersona

# ---------------------------------------------------------------------------
# Entradas y salidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaCrearPersona:
    cedula: str
    nombres: str
    apellidos: str
    email_institucional: str | None = None
    email_personal: str | None = None
    telefono: str | None = None
    tipo_vinculacion: TipoVinculacion = TipoVinculacion.OTRO
    unidad: str | None = None
    cargo: str | None = None
    codigo_empleado: str | None = None
    fecha_ingreso: date | None = None
    fecha_nacimiento: date | None = None
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaActualizarPersona:
    persona_id: UUID
    nombres: str | None = None
    apellidos: str | None = None
    email_institucional: str | None = None
    email_personal: str | None = None
    telefono: str | None = None
    tipo_vinculacion: TipoVinculacion | None = None
    unidad: str | None = None
    cargo: str | None = None
    codigo_empleado: str | None = None
    fecha_ingreso: date | None = None
    fecha_nacimiento: date | None = None
    observaciones: str | None = None
    activo: bool | None = None


@dataclass(frozen=True, slots=True)
class EntradaListarPersonas:
    filtro: FiltroPersonas = field(default_factory=FiltroPersonas)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class PersonaConTitulos:
    """Vista de detalle: la persona y su expediente academico."""

    persona: Persona
    titulos: list[Titulo] = field(default_factory=list)

    @property
    def total_titulos(self) -> int:
        return len(self.titulos)

    @property
    def titulos_vigentes(self) -> int:
        from app.domain.enums import EstadoTitulo

        return sum(1 for t in self.titulos if t.estado is EstadoTitulo.VIGENTE)


@dataclass(frozen=True, slots=True)
class FilaImportacion:
    """Una fila del archivo de carga masiva."""

    cedula: str
    nombres: str
    apellidos: str
    email_institucional: str | None = None
    tipo_vinculacion: str | None = None
    unidad: str | None = None
    cargo: str | None = None
    codigo_empleado: str | None = None


@dataclass(frozen=True, slots=True)
class ErrorImportacion:
    fila: int
    cedula: str
    motivo: str


@dataclass(frozen=True, slots=True)
class ResultadoImportacion:
    """Informe de una carga masiva. Nunca falla entera por una fila mala."""

    total_filas: int
    creadas: int
    duplicadas: int
    rechazadas: list[ErrorImportacion] = field(default_factory=list)

    @property
    def exitosa(self) -> bool:
        return not self.rechazadas


# ---------------------------------------------------------------------------
# Casos de uso
# ---------------------------------------------------------------------------


class CrearPersona(CasoDeUso[EntradaCrearPersona, Persona]):
    """Registra un empleado."""

    nombre = "personas.crear"
    descripcion = "Registra una persona (empleado) en el sistema"
    permiso_requerido = Permiso.PERSONAS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaCrearPersona, contexto: ContextoEjecucion) -> Persona:
        cedula = Cedula(entrada.cedula)

        async with self._uow:
            if await self._uow.personas.existe_cedula(cedula):
                raise YaExiste("persona", "cedula", cedula.valor)

            persona = Persona(
                cedula=cedula,
                nombre=NombrePersona(nombres=entrada.nombres, apellidos=entrada.apellidos),
                email_institucional=Email(entrada.email_institucional)
                if entrada.email_institucional
                else None,
                email_personal=Email(entrada.email_personal) if entrada.email_personal else None,
                telefono=entrada.telefono,
                tipo_vinculacion=entrada.tipo_vinculacion,
                unidad=entrada.unidad,
                cargo=entrada.cargo,
                codigo_empleado=entrada.codigo_empleado,
                fecha_ingreso=entrada.fecha_ingreso,
                fecha_nacimiento=entrada.fecha_nacimiento,
                observaciones=entrada.observaciones,
                creado_por=contexto.actor_id,
            )
            creada = await self._uow.personas.agregar(persona)
            await self._uow.commit()
            return creada


class ActualizarPersona(CasoDeUso[EntradaActualizarPersona, Persona]):
    """Modifica los datos de un empleado.

    La cedula no es modificable: es la identidad de la persona frente al
    registro nacional y cambiarla invalidaria todo su historico de consultas. Un
    error de digitacion se corrige eliminando y volviendo a crear.
    """

    nombre = "personas.actualizar"
    descripcion = "Actualiza los datos de una persona"
    permiso_requerido = Permiso.PERSONAS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarPersona, contexto: ContextoEjecucion
    ) -> Persona:
        async with self._uow:
            persona = await self._uow.personas.obtener(entrada.persona_id)
            if persona is None:
                raise NoEncontrado("Persona", entrada.persona_id)

            nombre = None
            if entrada.nombres is not None or entrada.apellidos is not None:
                nombre = NombrePersona(
                    nombres=entrada.nombres or persona.nombre.nombres,
                    apellidos=entrada.apellidos or persona.nombre.apellidos,
                )

            persona.actualizar_datos(
                nombre=nombre,
                email_institucional=Email(entrada.email_institucional)
                if entrada.email_institucional
                else None,
                email_personal=Email(entrada.email_personal) if entrada.email_personal else None,
                telefono=entrada.telefono,
                tipo_vinculacion=entrada.tipo_vinculacion,
                unidad=entrada.unidad,
                cargo=entrada.cargo,
                codigo_empleado=entrada.codigo_empleado,
                fecha_ingreso=entrada.fecha_ingreso,
                fecha_nacimiento=entrada.fecha_nacimiento,
                observaciones=entrada.observaciones,
            )

            if entrada.activo is not None:
                persona.activar() if entrada.activo else persona.desactivar()

            actualizada = await self._uow.personas.actualizar(persona)
            await self._uow.commit()
            return actualizada


class ObtenerPersona(CasoDeUso[UUID, PersonaConTitulos]):
    """Detalle de una persona con su expediente academico."""

    nombre = "personas.obtener"
    descripcion = "Obtiene una persona con todos sus titulos"
    permiso_requerido = Permiso.PERSONAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> PersonaConTitulos:
        async with self._uow:
            persona = await self._uow.personas.obtener(entrada)
            if persona is None:
                raise NoEncontrado("Persona", entrada)
            titulos = await self._uow.titulos.listar_por_persona(persona.id)
            return PersonaConTitulos(persona=persona, titulos=titulos)


class ObtenerPersonaPorCedula(CasoDeUso[str, PersonaConTitulos]):
    """Busqueda directa por cedula, la via natural del personal de ventanilla."""

    nombre = "personas.obtener_por_cedula"
    descripcion = "Busca una persona por su numero de cedula"
    permiso_requerido = Permiso.PERSONAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: str, contexto: ContextoEjecucion) -> PersonaConTitulos:
        cedula = Cedula(entrada)
        async with self._uow:
            persona = await self._uow.personas.obtener_por_cedula(cedula)
            if persona is None:
                raise NoEncontrado("Persona", cedula.valor)
            titulos = await self._uow.titulos.listar_por_persona(persona.id)
            return PersonaConTitulos(persona=persona, titulos=titulos)


class ListarPersonas(CasoDeUso[EntradaListarPersonas, Pagina[Persona]]):
    nombre = "personas.listar"
    descripcion = "Lista personas con filtros de busqueda y paginacion"
    permiso_requerido = Permiso.PERSONAS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarPersonas, contexto: ContextoEjecucion
    ) -> Pagina[Persona]:
        async with self._uow:
            return await self._uow.personas.listar(entrada.filtro, entrada.paginacion)


class EliminarPersona(CasoDeUso[UUID, None]):
    """Elimina una persona sin titulos ni historico.

    Si ya tiene expediente, se rechaza: borrarla destruiria evidencia de
    validacion. La via correcta en ese caso es desactivarla.
    """

    nombre = "personas.eliminar"
    descripcion = "Elimina una persona que no tenga titulos ni consultas"
    permiso_requerido = Permiso.PERSONAS_ELIMINAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            persona = await self._uow.personas.obtener(entrada)
            if persona is None:
                raise NoEncontrado("Persona", entrada)

            if await self._uow.titulos.contar_por_persona(persona.id) > 0:
                raise ReglaDeNegocioViolada(
                    "La persona tiene titulos registrados. Desactivela en lugar de "
                    "eliminarla para conservar la trazabilidad."
                )
            if persona.total_consultas > 0:
                raise ReglaDeNegocioViolada(
                    "La persona tiene historico de consultas. Desactivela en lugar de eliminarla."
                )

            await self._uow.personas.eliminar(persona.id)
            await self._uow.commit()


class ImportarPersonas(CasoDeUso[list[FilaImportacion], ResultadoImportacion]):
    """Carga masiva desde un archivo.

    Politica de fallos: una fila invalida no aborta la carga. Se informa fila a
    fila para que el responsable corrija el archivo de origen — con miles de
    registros, un "todo o nada" hace la herramienta inutilizable.
    """

    nombre = "personas.importar"
    descripcion = "Carga masiva de personas desde un archivo"
    permiso_requerido = Permiso.PERSONAS_IMPORTAR

    def __init__(self, uow: UnidadDeTrabajo, tamano_lote: int = 500) -> None:
        self._uow = uow
        self._lote = tamano_lote

    async def _ejecutar(
        self, entrada: list[FilaImportacion], contexto: ContextoEjecucion
    ) -> ResultadoImportacion:
        rechazadas: list[ErrorImportacion] = []
        aceptadas: list[Persona] = []
        duplicadas = 0
        vistas: set[str] = set()

        async with self._uow:
            for indice, fila in enumerate(entrada, start=1):
                try:
                    cedula = Cedula(fila.cedula)
                except ErrorValidacion as exc:
                    rechazadas.append(ErrorImportacion(indice, fila.cedula, exc.mensaje))
                    continue

                # Duplicado dentro del propio archivo.
                if cedula.valor in vistas:
                    duplicadas += 1
                    continue
                vistas.add(cedula.valor)

                if await self._uow.personas.existe_cedula(cedula):
                    duplicadas += 1
                    continue

                try:
                    aceptadas.append(self._construir(fila, cedula, contexto))
                except ErrorValidacion as exc:
                    rechazadas.append(ErrorImportacion(indice, cedula.valor, exc.mensaje))

            creadas = 0
            for inicio in range(0, len(aceptadas), self._lote):
                creadas += await self._uow.personas.agregar_muchas(
                    aceptadas[inicio : inicio + self._lote]
                )
            await self._uow.commit()

        return ResultadoImportacion(
            total_filas=len(entrada),
            creadas=creadas,
            duplicadas=duplicadas,
            rechazadas=rechazadas,
        )

    @staticmethod
    def _construir(fila: FilaImportacion, cedula: Cedula, contexto: ContextoEjecucion) -> Persona:
        vinculacion = TipoVinculacion.OTRO
        if fila.tipo_vinculacion:
            try:
                vinculacion = TipoVinculacion(fila.tipo_vinculacion.strip().upper())
            except ValueError:
                vinculacion = TipoVinculacion.OTRO

        return Persona(
            cedula=cedula,
            nombre=NombrePersona(nombres=fila.nombres, apellidos=fila.apellidos),
            email_institucional=Email(fila.email_institucional)
            if fila.email_institucional
            else None,
            tipo_vinculacion=vinculacion,
            unidad=fila.unidad,
            cargo=fila.cargo,
            codigo_empleado=fila.codigo_empleado,
            creado_por=contexto.actor_id,
        )
