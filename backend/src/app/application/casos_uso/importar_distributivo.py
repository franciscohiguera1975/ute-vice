"""Importacion del consolidado de distributivo docente.

Toma las filas crudas que leyo el lector y las convierte en catalogos, docentes
y filas del distributivo.

Tres decisiones de normalizacion, tomadas al contrastar el consolidado historico
2020-1 → 2026-1:

1. **Las sedes se unifican.** El origen escribe la misma sede de varias formas
   —`QUITO` y `SEDE QUITO`, o `MON`, `RHO` y `RICARDO HIDALGO OTTOLENGHI`, que
   son el mismo campus—. Sin unificarlas, agrupar por sede entre anios daria
   cifras partidas.
2. **La facultad NO se unifica.** En 2026-1 desaparecen FO, FCIC, CEL y ETECH
   porque hubo una reestructuracion real de facultades, no un error de captura.
   Normalizarlas borraria ese hecho del historico.
3. **Los titulos se separan.** El origen concatena hasta doce en una celda con
   ` & `; guardarla tal cual haria imposible buscar por titulo.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.core.logging import get_logger
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente, FilaDistributivo, separar_titulos
from app.domain.enums import Permiso
from app.domain.errors import ErrorValidacion
from app.domain.ports.importacion import (
    AvisoConsolidacion,
    ErrorImportacionDistributivo,
    FilaCrudaDistributivo,
    ResultadoImportacionDistributivo,
)
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import normalizar_texto
from app.domain.value_objects_distributivo import (
    DistribucionHoras,
    Identificacion,
    PeriodoAcademico,
)

log = get_logger(__name__)

#: Nombres con que el origen escribe cada sede. `MON`, `RHO` y
#: `RICARDO HIDALGO OTTOLENGHI` son el mismo campus.
ALIAS_SEDE: dict[str, str] = {
    "QUITO": "QUITO",
    "SEDE QUITO": "QUITO",
    "UIO": "QUITO",
    "SANTO DOMINGO": "SANTO DOMINGO",
    "SEDE SANTO DOMINGO": "SANTO DOMINGO",
    "SD": "SANTO DOMINGO",
    "MON": "MON",
    "RHO": "MON",
    "RICARDO HIDALGO OTTOLENGHI": "MON",
    "CUENCA": "CUENCA",
    "CAMPUS CUENCA": "CUENCA",
}

#: El origen escribe el genero de cuatro formas. Se unifican por el mismo
#: motivo que las sedes: sin ello, un conteo por genero saldria partido en
#: cuatro grupos donde hay dos.
ALIAS_GENERO: dict[str, str] = {
    "MASCULINO": "MASCULINO",
    "HOMBRE": "MASCULINO",
    "M": "MASCULINO",
    "FEMENINO": "FEMENINO",
    "MUJER": "FEMENINO",
    "F": "FEMENINO",
}

NOMBRES_GENERO: dict[str, str] = {"MASCULINO": "Masculino", "FEMENINO": "Femenino"}

#: Nombre legible de cada sede, para los selectores y el reporte.
NOMBRES_SEDE: dict[str, str] = {
    "QUITO": "Quito",
    "SANTO DOMINGO": "Santo Domingo",
    "MON": "Monjas (Ricardo Hidalgo Ottolenghi)",
    "CUENCA": "Cuenca",
}

#: Clave natural de una fila: docente, periodo, carrera y sede. La sede entra
#: porque un docente si dicta la misma carrera en dos campus el mismo periodo.
_ClaveNatural = tuple[UUID, UUID, UUID, UUID | None]

#: Valores que el origen usa para decir «sin dato».
_AUSENTES = {"", "NA", "N/A", "0", "-", "NO CONSTA", "NINGUNO"}


def _normalizar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(str(valor).split()).upper()
    return None if limpio in _AUSENTES else limpio


def _normalizar_sede(valor: str | None) -> str | None:
    limpio = _normalizar(valor)
    return ALIAS_SEDE.get(limpio, limpio) if limpio else None


def _normalizar_genero(valor: str | None) -> str | None:
    limpio = _normalizar(valor)
    return ALIAS_GENERO.get(limpio, limpio) if limpio else None


@dataclass(frozen=True, slots=True)
class EntradaImportacion:
    filas: tuple[FilaCrudaDistributivo, ...]
    crear_catalogos_faltantes: bool = True
    """Si es `False`, una fila que cite un valor desconocido se rechaza."""
    tamano_lote: int = 1000


class _Catalogos:
    """Cache de los doce catalogos durante una importacion.

    Resuelve codigo → id en memoria. Sin ella, una carga de 15.000 filas haria
    una consulta por cada valor de cada fila: cientos de miles de viajes a la
    base para resolver doce catalogos que caben holgadamente en un diccionario.
    """

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow
        self._por_tipo: dict[TipoCatalogo, dict[str, UUID]] = {}
        self._nuevos: list[ElementoCatalogo] = []
        self.creados: Counter[str] = Counter()

    async def cargar(self) -> None:
        for tipo in TipoCatalogo:
            elementos = await self._uow.catalogos.listar_todos(tipo, solo_activos=False)
            self._por_tipo[tipo] = {e.codigo: e.id for e in elementos}

    def resolver(
        self, tipo: TipoCatalogo, codigo: str | None, *, nombre: str | None = None
    ) -> UUID | None:
        """Devuelve el id del elemento, creandolo si hace falta."""
        if not codigo:
            return None

        clave = " ".join(codigo.split()).upper()
        existente = self._por_tipo[tipo].get(clave)
        if existente is not None:
            return existente

        elemento = ElementoCatalogo(
            tipo=tipo,
            codigo=clave,
            nombre=nombre or _titulo_legible(clave),
            orden=len(self._por_tipo[tipo]),
        )
        self._por_tipo[tipo][elemento.codigo] = elemento.id
        self._nuevos.append(elemento)
        self.creados[tipo.value] += 1
        return elemento.id

    def conoce(self, tipo: TipoCatalogo, codigo: str | None) -> bool:
        if not codigo:
            return True
        return " ".join(codigo.split()).upper() in self._por_tipo[tipo]

    async def persistir(self) -> None:
        if self._nuevos:
            await self._uow.catalogos.agregar_muchos(self._nuevos)
            self._nuevos = []


def _titulo_legible(codigo: str) -> str:
    """`MAESTRÍA EN X` → `Maestría en X`, respetando las siglas cortas."""
    if len(codigo) <= 6 and " " not in codigo:
        return codigo  # siglas de facultad: FCSEE, PEL, FO
    menores = {"DE", "EN", "Y", "DEL", "LA", "EL", "LOS", "LAS", "CON", "A", "POR"}
    palabras = codigo.split()
    return " ".join(
        p.capitalize() if i == 0 or p not in menores else p.lower() for i, p in enumerate(palabras)
    )


class ImportarDistributivo(CasoDeUso[EntradaImportacion, ResultadoImportacionDistributivo]):
    """Carga un consolidado completo.

    Politica de fallos: una fila invalida no aborta la carga. Se informa fila a
    fila, igual que en la importacion de personas: con 15.000 registros, un
    «todo o nada» convierte cualquier dato sucio en un bloqueo total.
    """

    nombre = "distributivo.importar"
    descripcion = "Importa un consolidado de distributivo docente"
    permiso_requerido = Permiso.DISTRIBUTIVO_IMPORTAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaImportacion, contexto: ContextoEjecucion
    ) -> ResultadoImportacionDistributivo:
        if not entrada.filas:
            raise ErrorValidacion("No hay filas que importar", campo="filas")

        resultado = ResultadoImportacionDistributivo(total_filas_leidas=len(entrada.filas))

        async with self._uow:
            catalogos = _Catalogos(self._uow)
            await catalogos.cargar()

            validas = self._validar(entrada, catalogos, resultado)
            docentes_por_id = await self._sincronizar_docentes(validas, catalogos, resultado)
            await catalogos.persistir()
            await self._uow.flush()

            await self._crear_filas(
                validas, catalogos, docentes_por_id, entrada, contexto, resultado
            )
            await self._uow.commit()

        log.info("Importacion de distributivo completada", extra={"resumen": resultado.resumen()})
        return resultado

    # ------------------------------------------------------------ validacion
    def _validar(
        self,
        entrada: EntradaImportacion,
        catalogos: _Catalogos,
        resultado: ResultadoImportacionDistributivo,
    ) -> list[FilaCrudaDistributivo]:
        validas: list[FilaCrudaDistributivo] = []

        for fila in entrada.filas:
            try:
                Identificacion(fila.identificacion)
            except ErrorValidacion as exc:
                resultado.rechazadas.append(
                    ErrorImportacionDistributivo(fila.numero_fila, fila.identificacion, exc.mensaje)
                )
                continue

            try:
                PeriodoAcademico.desde_codigo(fila.pao)
            except ErrorValidacion as exc:
                resultado.rechazadas.append(
                    ErrorImportacionDistributivo(fila.numero_fila, fila.identificacion, exc.mensaje)
                )
                continue

            if not _normalizar(fila.facultad):
                resultado.rechazadas.append(
                    ErrorImportacionDistributivo(
                        fila.numero_fila, fila.identificacion, "La facultad es obligatoria"
                    )
                )
                continue

            if not _normalizar(fila.carrera):
                resultado.rechazadas.append(
                    ErrorImportacionDistributivo(
                        fila.numero_fila,
                        fila.identificacion,
                        "La carrera es obligatoria y viene vacia",
                    )
                )
                continue

            if not entrada.crear_catalogos_faltantes:
                desconocido = self._primer_desconocido(fila, catalogos)
                if desconocido:
                    resultado.rechazadas.append(
                        ErrorImportacionDistributivo(
                            fila.numero_fila, fila.identificacion, desconocido
                        )
                    )
                    continue

            validas.append(fila)

        return validas

    @staticmethod
    def _primer_desconocido(fila: FilaCrudaDistributivo, catalogos: _Catalogos) -> str | None:
        comprobaciones = (
            (TipoCatalogo.PAO, fila.pao),
            (TipoCatalogo.FACULTAD, _normalizar(fila.facultad)),
            (TipoCatalogo.CARRERA, _normalizar(fila.carrera)),
            (TipoCatalogo.SEDE, _normalizar_sede(fila.sede)),
            (TipoCatalogo.NIVEL, _normalizar(fila.nivel)),
        )
        for tipo, codigo in comprobaciones:
            if not catalogos.conoce(tipo, codigo):
                return f"Valor desconocido en {tipo.singular}: '{codigo}'"
        return None

    # ------------------------------------------------------------- docentes
    async def _sincronizar_docentes(
        self,
        filas: list[FilaCrudaDistributivo],
        catalogos: _Catalogos,
        resultado: ResultadoImportacionDistributivo,
    ) -> dict[str, UUID]:
        """Crea los docentes que faltan y devuelve identificacion → id."""
        nombres: dict[str, Counter[str]] = defaultdict(Counter)
        generos: dict[str, Counter[str]] = defaultdict(Counter)
        titulos: dict[str, list[str]] = defaultdict(list)

        for fila in filas:
            clave = Identificacion(fila.identificacion).valor
            if nombre := _normalizar(fila.nombre):
                nombres[clave][nombre] += 1
            if genero := _normalizar_genero(fila.genero):
                generos[clave][genero] += 1
            for titulo in separar_titulos(fila.titulo):
                if titulo not in titulos[clave]:
                    titulos[clave].append(titulo)

        por_identificacion: dict[str, UUID] = {}
        nuevos: list[Docente] = []

        for clave in {Identificacion(f.identificacion).valor for f in filas}:
            existente = await self._uow.docentes.obtener_por_identificacion(clave)
            if existente is not None:
                por_identificacion[clave] = existente.id
                resultado.docentes_existentes += 1
                continue

            docente = Docente(
                identificacion=Identificacion(clave),
                nombre_completo=self._mejor_nombre(nombres[clave]) or clave,
                genero_id=self._resolver_genero(catalogos, self._mas_frecuente(generos[clave])),
                titulos_ids=[
                    id_titulo
                    for titulo in titulos[clave]
                    if (
                        id_titulo := catalogos.resolver(
                            TipoCatalogo.TITULO_PROFESIONAL, titulo, nombre=titulo
                        )
                    )
                    is not None
                ],
            )
            nuevos.append(docente)
            por_identificacion[clave] = docente.id

        # Los titulos deben existir antes de enlazarlos con los docentes.
        await catalogos.persistir()
        await self._uow.flush()

        resultado.titulos_creados = catalogos.creados.get(TipoCatalogo.TITULO_PROFESIONAL.value, 0)
        if nuevos:
            resultado.docentes_creados = await self._uow.docentes.agregar_muchos(nuevos)
        return por_identificacion

    @staticmethod
    def _resolver_genero(catalogos: _Catalogos, codigo: str | None) -> UUID | None:
        if not codigo:
            return None
        return catalogos.resolver(
            TipoCatalogo.GENERO, codigo, nombre=NOMBRES_GENERO.get(codigo, _titulo_legible(codigo))
        )

    @staticmethod
    def _mejor_nombre(variantes: Counter[str]) -> str | None:
        """La grafia mas frecuente; a igualdad, la mas completa.

        El origen trae hasta tres grafias del mismo docente entre periodos
        (`GUTIÉRREZ` y `GUTIERREZ`). Elegir siempre la misma hace que la persona
        sea un solo texto en todo el historico.
        """
        if not variantes:
            return None
        return max(variantes.items(), key=lambda par: (par[1], len(par[0])))[0]

    @staticmethod
    def _mas_frecuente(variantes: Counter[str]) -> str | None:
        return variantes.most_common(1)[0][0] if variantes else None

    # ---------------------------------------------------------------- filas
    async def _crear_filas(
        self,
        filas: list[FilaCrudaDistributivo],
        catalogos: _Catalogos,
        docentes: dict[str, UUID],
        entrada: EntradaImportacion,
        contexto: ContextoEjecucion,
        resultado: ResultadoImportacionDistributivo,
    ) -> None:
        agrupadas: dict[_ClaveNatural, list[FilaCrudaDistributivo]] = defaultdict(list)
        referencias: dict[_ClaveNatural, FilaCrudaDistributivo] = {}

        for fila in filas:
            clave_doc = Identificacion(fila.identificacion).valor
            pao_id = catalogos.resolver(TipoCatalogo.PAO, fila.pao)
            carrera_id = catalogos.resolver(TipoCatalogo.CARRERA, _normalizar(fila.carrera))
            # `_validar` ya garantizo que ambos vienen informados; la comprobacion
            # esta para que el tipo sea cierto y no una promesa.
            if pao_id is None or carrera_id is None:  # pragma: no cover
                continue

            natural: _ClaveNatural = (
                docentes[clave_doc],
                pao_id,
                carrera_id,
                self._resolver_sede(catalogos, fila.sede),
            )
            agrupadas[natural].append(fila)
            referencias.setdefault(natural, fila)

        construidas: list[FilaDistributivo] = []
        for natural, grupo in agrupadas.items():
            docente_id, pao_id, carrera_id, sede_id = natural
            principal = referencias[natural]

            horas = self._sumar_horas(grupo)
            if len(grupo) > 1:
                resultado.filas_consolidadas += len(grupo) - 1
                resultado.consolidaciones.append(
                    AvisoConsolidacion(
                        identificacion=principal.identificacion,
                        pao=principal.pao,
                        carrera=principal.carrera or "",
                        sede=_normalizar_sede(principal.sede),
                        filas_origen=tuple(f.numero_fila for f in grupo),
                        total_horas_resultante=horas.total,
                    )
                )

            facultad_id = catalogos.resolver(TipoCatalogo.FACULTAD, _normalizar(principal.facultad))
            if facultad_id is None:  # pragma: no cover
                continue

            construidas.append(
                FilaDistributivo(
                    docente_id=docente_id,
                    pao_id=pao_id,
                    facultad_id=facultad_id,
                    carrera_id=carrera_id,
                    sede_id=sede_id,
                    nivel_id=catalogos.resolver(TipoCatalogo.NIVEL, _normalizar(principal.nivel)),
                    titularidad_id=catalogos.resolver(
                        TipoCatalogo.TITULARIDAD, _normalizar(principal.titularidad)
                    ),
                    dedicacion_id=catalogos.resolver(
                        TipoCatalogo.DEDICACION, _normalizar(principal.dedicacion)
                    ),
                    categoria_id=catalogos.resolver(
                        TipoCatalogo.CATEGORIA, _normalizar(principal.categoria)
                    ),
                    tipo_titulo_id=catalogos.resolver(
                        TipoCatalogo.TIPO_TITULO, _normalizar(principal.tipo_titulo)
                    ),
                    horas=horas,
                    medida=principal.medida,
                    creado_por=contexto.actor_id,
                )
            )

        await catalogos.persistir()
        await self._uow.flush()
        resultado.elementos_catalogo_creados = dict(catalogos.creados)

        for inicio in range(0, len(construidas), entrada.tamano_lote):
            lote = construidas[inicio : inicio + entrada.tamano_lote]
            resultado.filas_creadas += await self._uow.distributivo.agregar_muchas(lote)

    @staticmethod
    def _resolver_sede(catalogos: _Catalogos, sede: str | None) -> UUID | None:
        codigo = _normalizar_sede(sede)
        if not codigo:
            return None
        return catalogos.resolver(
            TipoCatalogo.SEDE, codigo, nombre=NOMBRES_SEDE.get(codigo, _titulo_legible(codigo))
        )

    @staticmethod
    def _sumar_horas(grupo: list[FilaCrudaDistributivo]) -> DistribucionHoras:
        """Suma las horas de las filas que comparten la clave natural.

        Ocurre en el 0,5% del consolidado: el origen trae la misma carga dos
        veces con repartos distintos. Se suman en lugar de quedarse con una,
        porque el total es el dato que la institucion reporta; cada fusion se
        informa aparte para que alguien pueda revisarla.
        """
        acumulado: dict[str, float] = defaultdict(float)
        for fila in grupo:
            for clave, valor in fila.horas.items():
                acumulado[clave] += valor
        return DistribucionHoras.desde_plano(dict(acumulado))


def clave_normalizada(texto: str) -> str:
    return normalizar_texto(texto)
