"""Alta de personas a partir del padron docente.

El distributivo trae tres mil docentes con su cedula y su nombre. El modulo de
personas —que es el que consulta al registro nacional— empezaba vacio y habia
que cargarlo aparte, con los mismos datos y a mano.

Este caso de uso los cruza: por cada docente crea su persona si no existe, la
enlaza si ya estaba, y deja el `persona_id` puesto en el docente. Es idempotente:
correrlo dos veces no duplica a nadie.

**No todos pueden pasar.** `Persona` exige una cedula ecuatoriana valida porque
es con lo que se consulta al SENESCYT, y el padron docente incluye extranjeros
con pasaporte. Esos quedan fuera y se informan: no es un fallo, es que no hay
nada que consultar por ellos en el registro nacional.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.persona import Persona
from app.domain.enums import Permiso, TipoVinculacion
from app.domain.errors import ErrorValidacion
from app.domain.ports.repositorios import Paginacion
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import Cedula, NombrePersona

#: Cuantos apellidos lleva un nombre ecuatoriano. El padron los escribe como
#: «APELLIDO APELLIDO NOMBRE NOMBRE», que es el orden de los documentos.
_APELLIDOS = 2


@dataclass(frozen=True, slots=True)
class ResultadoSincronizacion:
    personas_creadas: int = 0
    docentes_enlazados: int = 0
    """Docentes cuya persona ya existia: se enlazaron, no se duplicaron."""

    ya_estaban: int = 0
    sin_cedula: int = 0
    """Docentes con pasaporte. No pueden ser personas: ver el modulo."""

    problemas: list[str] = field(default_factory=list)

    @property
    def resumen(self) -> str:
        return (
            f"{self.personas_creadas} creadas · {self.docentes_enlazados} enlazadas · "
            f"{self.ya_estaban} ya estaban · {self.sin_cedula} con pasaporte"
        )


def separar_nombre(completo: str) -> NombrePersona:
    """«ABARCA ACHIG MARITZA CATALINA» → apellidos «Abarca Achig».

    Con cuatro palabras —el 90 % del padron— la division es exacta. Con tres,
    se asume un solo nombre; con dos, un apellido y un nombre. No hay forma de
    acertar siempre: el origen guarda una sola cadena y no marca donde termina
    el apellido.
    """
    palabras = completo.split()
    if len(palabras) < 2:
        raise ErrorValidacion(
            f"El nombre '{completo}' no permite separar apellidos de nombres",
            campo="nombre_completo",
        )

    corte = 1 if len(palabras) == 2 else _APELLIDOS
    return NombrePersona(
        apellidos=" ".join(palabras[:corte]),
        nombres=" ".join(palabras[corte:]),
    )


class SincronizarPersonasDesdeDocentes(CasoDeUso[None, ResultadoSincronizacion]):
    """Crea y enlaza las personas del padron docente."""

    nombre = "personas.sincronizar_desde_docentes"
    descripcion = "Crea registros de personas a partir del padron docente"
    permiso_requerido = Permiso.PERSONAS_IMPORTAR

    #: Los docentes se recorren por paginas para no cargar tres mil entidades
    #: —con sus titulos— de una vez en un servidor de 1,8 GB.
    TAMANO_PAGINA = 200

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: None, contexto: ContextoEjecucion
    ) -> ResultadoSincronizacion:
        from app.domain.ports.distributivo import FiltroDocentes

        creadas = enlazados = ya_estaban = sin_cedula = 0
        problemas: list[str] = []

        async with self._uow:
            unidades = await self._uow.distributivo.unidades_por_docente()

            pagina_actual = 1
            while True:
                pagina = await self._uow.docentes.listar(
                    FiltroDocentes(), Paginacion(pagina=pagina_actual, tamano=self.TAMANO_PAGINA)
                )
                if not pagina.items:
                    break

                for docente in pagina.items:
                    if docente.persona_id is not None:
                        ya_estaban += 1
                        continue
                    if not docente.identificacion.es_cedula:
                        sin_cedula += 1
                        continue

                    cedula = Cedula(docente.identificacion.valor)
                    existente = await self._uow.personas.obtener_por_cedula(cedula)
                    if existente is not None:
                        docente.persona_id = existente.id
                        await self._uow.docentes.actualizar(docente)
                        enlazados += 1
                        continue

                    try:
                        nombre = separar_nombre(docente.nombre_completo)
                    except ErrorValidacion as error:
                        problemas.append(f"{docente.identificacion.valor}: {error}")
                        continue

                    persona = await self._uow.personas.agregar(
                        Persona(
                            cedula=cedula,
                            nombre=nombre,
                            tipo_vinculacion=TipoVinculacion.DOCENTE,
                            unidad=unidades.get(docente.id),
                            creado_por=contexto.actor_id,
                        )
                    )
                    docente.persona_id = persona.id
                    await self._uow.docentes.actualizar(docente)
                    creadas += 1

                if pagina_actual * self.TAMANO_PAGINA >= pagina.total:
                    break
                pagina_actual += 1

            await self._uow.commit()

        return ResultadoSincronizacion(
            personas_creadas=creadas,
            docentes_enlazados=enlazados,
            ya_estaban=ya_estaban,
            sin_cedula=sin_cedula,
            problemas=problemas,
        )
