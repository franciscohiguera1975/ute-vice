"""Traduccion entre los modelos ORM del distributivo y las entidades de dominio."""

from __future__ import annotations

from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente, FilaDistributivo
from app.domain.enums import EstadoValidacion
from app.domain.value_objects import normalizar_texto
from app.domain.value_objects_distributivo import DistribucionHoras, Identificacion
from app.infrastructure.db.base import Base
from app.infrastructure.db.modelos_distributivo import (
    MODELOS_CATALOGO,
    DocenteModel,
    FilaDistributivoModel,
)

#: Camino inverso de `MODELOS_CATALOGO`: de la tabla al tipo de catalogo. Lo usa
#: el mapeador para saber a que catalogo pertenece una fila que ya leyo.
TIPOS_POR_MODELO: dict[type[Base], TipoCatalogo] = {
    modelo: tipo for tipo, modelo in MODELOS_CATALOGO.items()
}


# ---------------------------------------------------------------------------
# Catalogos
# ---------------------------------------------------------------------------


def catalogo_a_dominio(modelo: Base, tipo: TipoCatalogo | None = None) -> ElementoCatalogo:
    return ElementoCatalogo(
        id=modelo.id,  # type: ignore[attr-defined]
        tipo=tipo or TIPOS_POR_MODELO[type(modelo)],
        codigo=modelo.codigo,  # type: ignore[attr-defined]
        nombre=modelo.nombre,  # type: ignore[attr-defined]
        descripcion=modelo.descripcion,  # type: ignore[attr-defined]
        activo=modelo.activo,  # type: ignore[attr-defined]
        orden=modelo.orden,  # type: ignore[attr-defined]
        codigo_erp=modelo.codigo_erp or "",  # type: ignore[attr-defined]
        atributos=dict(modelo.atributos or {}),  # type: ignore[attr-defined]
        creado_en=modelo.creado_en,  # type: ignore[attr-defined]
        actualizado_en=modelo.actualizado_en,  # type: ignore[attr-defined]
    )


def catalogo_a_modelo(entidad: ElementoCatalogo, modelo: Base | None = None) -> Base:
    modelo = modelo or MODELOS_CATALOGO[entidad.tipo](id=entidad.id)
    modelo.codigo = entidad.codigo  # type: ignore[attr-defined]
    modelo.nombre = entidad.nombre  # type: ignore[attr-defined]
    modelo.descripcion = entidad.descripcion  # type: ignore[attr-defined]
    modelo.clave_busqueda = entidad.clave_busqueda  # type: ignore[attr-defined]
    modelo.activo = entidad.activo  # type: ignore[attr-defined]
    modelo.orden = entidad.orden  # type: ignore[attr-defined]
    modelo.codigo_erp = entidad.codigo_erp  # type: ignore[attr-defined]
    modelo.atributos = entidad.atributos  # type: ignore[attr-defined]
    return modelo


# ---------------------------------------------------------------------------
# Docentes
# ---------------------------------------------------------------------------


def docente_a_dominio(modelo: DocenteModel) -> Docente:
    return Docente(
        id=modelo.id,
        identificacion=Identificacion(modelo.identificacion),
        nombre_completo=modelo.nombre_completo,
        genero_id=modelo.genero_id,
        persona_id=modelo.persona_id,
        titulos_ids=[t.id for t in modelo.titulos],
        activo=modelo.activo,
        observaciones=modelo.observaciones,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def docente_a_modelo(entidad: Docente, modelo: DocenteModel | None = None) -> DocenteModel:
    modelo = modelo or DocenteModel(id=entidad.id)
    modelo.identificacion = entidad.identificacion.valor
    modelo.es_cedula = entidad.identificacion.es_cedula
    modelo.nombre_completo = entidad.nombre_completo
    modelo.clave_busqueda = entidad.clave_busqueda
    modelo.genero_id = entidad.genero_id
    modelo.persona_id = entidad.persona_id
    modelo.activo = entidad.activo
    modelo.observaciones = entidad.observaciones
    return modelo


# ---------------------------------------------------------------------------
# Filas del distributivo
# ---------------------------------------------------------------------------


def fila_a_dominio(modelo: FilaDistributivoModel) -> FilaDistributivo:
    return FilaDistributivo(
        id=modelo.id,
        docente_id=modelo.docente_id,
        pao_id=modelo.pao_id,
        facultad_id=modelo.facultad_id,
        carrera_id=modelo.carrera_id,
        sede_id=modelo.sede_id,
        nivel_id=modelo.nivel_id,
        titularidad_id=modelo.titularidad_id,
        dedicacion_id=modelo.dedicacion_id,
        categoria_id=modelo.categoria_id,
        tipo_titulo_id=modelo.tipo_titulo_id,
        horas=DistribucionHoras(
            docencia=dict(modelo.horas_docencia or {}),
            gestion=dict(modelo.horas_gestion or {}),
            investigacion=dict(modelo.horas_investigacion or {}),
            vinculacion=dict(modelo.horas_vinculacion or {}),
        ),
        medida=modelo.medida,
        observaciones=modelo.observaciones,
        estado_validacion=(
            EstadoValidacion(modelo.estado_validacion) if modelo.estado_validacion else None
        ),
        fase=modelo.fase,
        semanas=modelo.semanas,
        relacion_laboral=modelo.relacion_laboral,
        tutor_posgrado=bool(modelo.tutor_posgrado),
        tutor_medicina=bool(modelo.tutor_medicina),
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
        creado_por=modelo.creado_por,
    )


def fila_a_modelo(
    entidad: FilaDistributivo, modelo: FilaDistributivoModel | None = None
) -> FilaDistributivoModel:
    modelo = modelo or FilaDistributivoModel(id=entidad.id)
    modelo.docente_id = entidad.docente_id
    modelo.pao_id = entidad.pao_id
    modelo.facultad_id = entidad.facultad_id
    modelo.carrera_id = entidad.carrera_id
    modelo.sede_id = entidad.sede_id
    modelo.nivel_id = entidad.nivel_id
    modelo.titularidad_id = entidad.titularidad_id
    modelo.dedicacion_id = entidad.dedicacion_id
    modelo.categoria_id = entidad.categoria_id
    modelo.tipo_titulo_id = entidad.tipo_titulo_id

    modelo.horas_docencia = entidad.horas.docencia
    modelo.horas_gestion = entidad.horas.gestion
    modelo.horas_investigacion = entidad.horas.investigacion
    modelo.horas_vinculacion = entidad.horas.vinculacion

    # Los totales se recalculan al guardar, nunca se copian de la entrada: es lo
    # que garantiza que la columna y el detalle no puedan divergir.
    modelo.total_docencia = entidad.horas.total_docencia
    modelo.total_gestion = entidad.horas.total_gestion
    modelo.total_investigacion = entidad.horas.total_investigacion
    modelo.total_vinculacion = entidad.horas.total_vinculacion
    modelo.total_horas = entidad.horas.total

    modelo.medida = entidad.medida
    modelo.observaciones = entidad.observaciones

    modelo.estado_validacion = (
        entidad.estado_validacion.value if entidad.estado_validacion else None
    )
    modelo.fase = entidad.fase
    modelo.semanas = entidad.semanas
    modelo.relacion_laboral = entidad.relacion_laboral
    modelo.tutor_posgrado = entidad.tutor_posgrado
    modelo.tutor_medicina = entidad.tutor_medicina
    modelo.creado_por = entidad.creado_por
    return modelo


def clave_busqueda_docente(nombre: str, identificacion: str) -> str:
    return normalizar_texto(f"{nombre} {identificacion}")
