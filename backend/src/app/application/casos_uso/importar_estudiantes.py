"""Importacion del reporte de matricula estudiantil de Banner.

Toma las filas crudas que leyo el lector y las convierte en estudiantes,
matriculas y becas. Hermano del caso de uso de distributivo
(`app.application.casos_uso.importar_distributivo.ImportarDistributivo`):
misma politica de tolerancia fila a fila, y reutiliza su `CacheDeCatalogos`
para resolver -y crear al vuelo, si hace falta- el genero.

## El cruce con el catalogo de carreras

Es **por igualdad exacta de texto normalizado**, nunca por similitud difusa:
un intento anterior de emparejar por texto aproximado produjo falsos
positivos entre el padron de RRHH y la matriz de investigacion (ver la
memoria del proyecto, `distributivo-enriquecimiento-banner-senescyt.md`). Por
eso aqui se compara `CARRERA.strip().upper()` contra `cat_carreras.nombre`
-ya normalizado por `ElementoCatalogo.__post_init__`- y, sin coincidencia,
`carrera_id` queda `None`: la fila **no se rechaza** y **no se crea una
carrera nueva** -ese catalogo es responsabilidad del distributivo docente,
no de esta carga-. Se cuenta en `sin_carrera_reconocida` para que alguien lo
revise.

## Identidad del estudiante

`Estudiante.cedula` no es unica -Banner permite doble matricula el mismo
periodo con la misma cedula, en otra carrera o sede-, asi que la resolucion de
identidad es best-effort: se busca un estudiante existente por cedula
(`RepositorioEstudiantes.obtener_por_cedula`) y, si no hay, se crea uno. Dentro
de un mismo archivo, dos filas con la misma cedula comparten el mismo
`Estudiante` -son su doble matricula-, no dos personas distintas.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.application.casos_uso.importar_distributivo import CacheDeCatalogos
from app.core.logging import get_logger
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.entities.estudiantes import BecaEstudiante, Estudiante, MatriculaEstudiante
from app.domain.enums import Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.importacion_estudiantes import (
    ErrorImportacionEstudiante,
    FilaCrudaEstudiante,
    ResultadoImportacionEstudiantes,
)
from app.domain.ports.uow import UnidadDeTrabajo

log = get_logger(__name__)

#: Valores que el origen usa para decir «sin dato».
_AUSENTES = {"", "NA", "N/A", "0", "-"}


def _normalizar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(str(valor).split()).upper()
    return None if limpio in _AUSENTES else limpio


def _texto(valor: str | None) -> str | None:
    """Como `_normalizar`, pero sin forzar mayusculas: para los campos de
    texto crudo -sede, facultad, carrera- que se guardan tal como vienen."""
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return None if limpio.upper() in _AUSENTES else limpio


def _a_float(valor: str | None) -> float | None:
    if not valor:
        return None
    try:
        return float(valor.strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class EntradaImportacionEstudiantes:
    filas: tuple[FilaCrudaEstudiante, ...]
    tamano_lote: int = 1000


class _CacheCarreras:
    """Carreras del distributivo, indexadas por nombre normalizado.

    Se carga una sola vez por importacion: cruzar contra la base de datos
    fila a fila -quince mil veces en el reporte mas grande- serian quince mil
    consultas para lo que cabe en un diccionario.
    """

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow
        self._por_nombre: dict[str, UUID] = {}

    async def cargar(self) -> None:
        carreras = await self._uow.catalogos.listar_todos(TipoCatalogo.CARRERA, solo_activos=False)
        self._por_nombre = {c.nombre.strip().upper(): c.id for c in carreras}

    def resolver(self, carrera: str | None) -> UUID | None:
        if not carrera:
            return None
        return self._por_nombre.get(carrera.strip().upper())


class ImportarEstudiantes(
    CasoDeUso[EntradaImportacionEstudiantes, ResultadoImportacionEstudiantes]
):
    """Carga un reporte de matricula estudiantil completo.

    Politica de fallos: una fila invalida no aborta la carga -igual que en el
    distributivo-: se informa fila a fila en `resultado.rechazadas`.
    """

    nombre = "estudiantes.importar"
    descripcion = "Importa un reporte de matricula estudiantil de Banner"
    permiso_requerido = Permiso.ESTUDIANTES_IMPORTAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaImportacionEstudiantes, contexto: ContextoEjecucion
    ) -> ResultadoImportacionEstudiantes:
        if not entrada.filas:
            raise ErrorValidacion("No hay filas que importar", campo="filas")

        resultado = ResultadoImportacionEstudiantes(total_filas_leidas=len(entrada.filas))

        async with self._uow:
            carreras = _CacheCarreras(self._uow)
            await carreras.cargar()

            catalogos = CacheDeCatalogos(self._uow)
            await catalogos.cargar()

            validas = self._validar(entrada, resultado)

            estudiantes_por_cedula = await self._resolver_estudiantes(validas, catalogos, resultado)
            await catalogos.persistir()
            await self._uow.flush()
            resultado.generos_creados = catalogos.creados.get(TipoCatalogo.GENERO.value, 0)

            matriculas = self._construir_matriculas(
                validas, carreras, estudiantes_por_cedula, resultado
            )

            altas, cambios = await self._uow.estudiantes.importar_lote(
                list(estudiantes_por_cedula.values()), matriculas
            )
            resultado.matriculas_creadas = altas
            resultado.matriculas_actualizadas = cambios
            resultado.becas_creadas = sum(len(m.becas) for m in matriculas)

            await self._uow.commit()

        log.info(
            "Importacion de matricula estudiantil completada",
            extra={"resumen": resultado.resumen()},
        )
        return resultado

    # ------------------------------------------------------------ validacion
    def _validar(
        self, entrada: EntradaImportacionEstudiantes, resultado: ResultadoImportacionEstudiantes
    ) -> list[FilaCrudaEstudiante]:
        validas: list[FilaCrudaEstudiante] = []
        for fila in entrada.filas:
            cedula = _texto(fila.cedula)
            if not cedula:
                resultado.rechazadas.append(
                    ErrorImportacionEstudiante(
                        fila.numero_fila, fila.cedula, "La cedula es obligatoria"
                    )
                )
                continue
            if not _texto(fila.periodo):
                resultado.rechazadas.append(
                    ErrorImportacionEstudiante(
                        fila.numero_fila, cedula, "El periodo es obligatorio"
                    )
                )
                continue
            validas.append(fila)
        return validas

    # --------------------------------------------------------- estudiantes
    async def _resolver_estudiantes(
        self,
        filas: list[FilaCrudaEstudiante],
        catalogos: CacheDeCatalogos,
        resultado: ResultadoImportacionEstudiantes,
    ) -> dict[str, Estudiante]:
        """Un `Estudiante` por cedula distinta en el lote.

        Dos filas del mismo archivo con la misma cedula -doble matricula- se
        resuelven al mismo estudiante, no a dos personas distintas.
        """
        generos_por_cedula: dict[str, Counter[str]] = defaultdict(Counter)
        for fila in filas:
            cedula = _texto(fila.cedula) or ""
            if genero := _normalizar(fila.genero):
                generos_por_cedula[cedula][genero] += 1

        por_cedula: dict[str, Estudiante] = {}
        for fila in filas:
            cedula = _texto(fila.cedula) or ""
            if cedula in por_cedula:
                continue

            genero_dominante = self._mas_frecuente(generos_por_cedula[cedula])
            genero_id = (
                catalogos.resolver(TipoCatalogo.GENERO, genero_dominante, nombre=genero_dominante)
                if genero_dominante
                else None
            )

            existente = await self._uow.estudiantes.obtener_por_cedula(cedula)
            if existente is not None:
                existente.actualizar(
                    nombre=_texto(fila.nombre),
                    id_banner=_texto(fila.id_banner),
                    genero_id=genero_id,
                    mail_personal=_texto(fila.mail_personal),
                    mail_ute=_texto(fila.mail_ute),
                    telefono_celular=_texto(fila.telefono_celular),
                    telefono_fijo=_texto(fila.telefono_fijo),
                    fecha_nacimiento=fila.fecha_nacimiento,
                )
                por_cedula[cedula] = existente
                resultado.estudiantes_existentes += 1
                continue

            nuevo = Estudiante(
                cedula=cedula,
                nombre=_texto(fila.nombre) or cedula,
                id_banner=_texto(fila.id_banner),
                genero_id=genero_id,
                mail_personal=_texto(fila.mail_personal),
                mail_ute=_texto(fila.mail_ute),
                telefono_celular=_texto(fila.telefono_celular),
                telefono_fijo=_texto(fila.telefono_fijo),
                fecha_nacimiento=fila.fecha_nacimiento,
            )
            por_cedula[cedula] = nuevo
            resultado.estudiantes_creados += 1

        return por_cedula

    @staticmethod
    def _mas_frecuente(variantes: Counter[str]) -> str | None:
        return variantes.most_common(1)[0][0] if variantes else None

    # ----------------------------------------------------------- matriculas
    def _construir_matriculas(
        self,
        filas: list[FilaCrudaEstudiante],
        carreras: _CacheCarreras,
        estudiantes_por_cedula: dict[str, Estudiante],
        resultado: ResultadoImportacionEstudiantes,
    ) -> list[MatriculaEstudiante]:
        matriculas: list[MatriculaEstudiante] = []
        for fila in filas:
            cedula = _texto(fila.cedula) or ""
            estudiante = estudiantes_por_cedula[cedula]

            carrera_texto = _texto(fila.carrera)
            carrera_id = carreras.resolver(carrera_texto)
            if carrera_id is None and carrera_texto:
                resultado.sin_carrera_reconocida += 1

            becas = [
                BecaEstudiante(
                    codigo_beca=_texto(beca.codigo_beca),
                    financiamiento=_texto(beca.financiamiento),
                    tipo_beca=_texto(beca.tipo_beca),
                    porcentaje=_a_float(beca.porcentaje),
                )
                for beca in fila.becas
            ]

            matriculas.append(
                MatriculaEstudiante(
                    estudiante_id=estudiante.id,
                    periodo=_texto(fila.periodo) or "",
                    sede=_texto(fila.sede),
                    facultad=_texto(fila.facultad),
                    carrera=carrera_texto,
                    carrera_id=carrera_id,
                    tipo_carrera=_texto(fila.tipo_carrera),
                    modalidad=_texto(fila.modalidad),
                    nivel_formacion_1=_texto(fila.nivel_formacion_1),
                    nivel_formacion_2=_texto(fila.nivel_formacion_2),
                    tipo_estudiante=_texto(fila.tipo_estudiante),
                    sistema=_texto(fila.sistema),
                    matriculado=_texto(fila.matriculado),
                    solicitud_retiro=_texto(fila.solicitud_retiro),
                    bloqueo_plataforma=fila.bloqueo_plataforma,
                    estado=_texto(fila.estado),
                    becas=becas,
                )
            )
        return matriculas
