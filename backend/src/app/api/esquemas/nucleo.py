"""Esquemas de personas, titulos, consultas y tablero."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, field_validator

from app.api.esquemas.comunes import EsquemaBase
from app.application.casos_uso.consultas import ResultadoEjecucion
from app.application.casos_uso.personas import PersonaConTitulos
from app.domain.entities.consulta import ConsultaLog, JobCobertura
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import (
    EstadoConsulta,
    EstadoJob,
    EstadoTitulo,
    FormatoReporte,
    NivelTitulo,
    OrigenTitulo,
    TipoVinculacion,
)
from app.domain.ports.analitica import TableroCompleto
from app.domain.value_objects import Cedula

# ===========================================================================
# Personas
# ===========================================================================


class PersonaCrear(EsquemaBase):
    cedula: Annotated[str, Field(min_length=10, max_length=13)]
    nombres: Annotated[str, Field(min_length=1, max_length=120)]
    apellidos: Annotated[str, Field(min_length=1, max_length=120)]
    email_institucional: str | None = None
    email_personal: str | None = None
    telefono: str | None = Field(default=None, max_length=32)
    tipo_vinculacion: TipoVinculacion = TipoVinculacion.OTRO
    unidad: str | None = Field(default=None, max_length=160)
    cargo: str | None = Field(default=None, max_length=160)
    codigo_empleado: str | None = Field(default=None, max_length=40)
    fecha_ingreso: date | None = None
    fecha_nacimiento: date | None = None
    observaciones: str | None = None

    @field_validator("cedula")
    @classmethod
    def _validar_cedula(cls, valor: str) -> str:
        """Valida el digito verificador antes de tocar la base.

        Se hace aqui, en el borde, para devolver un 422 con el campo exacto en
        lugar de dejar que el error de dominio suba sin esa precision.
        """
        return Cedula(valor).valor


class PersonaActualizar(EsquemaBase):
    nombres: str | None = Field(default=None, max_length=120)
    apellidos: str | None = Field(default=None, max_length=120)
    email_institucional: str | None = None
    email_personal: str | None = None
    telefono: str | None = Field(default=None, max_length=32)
    tipo_vinculacion: TipoVinculacion | None = None
    unidad: str | None = Field(default=None, max_length=160)
    cargo: str | None = Field(default=None, max_length=160)
    codigo_empleado: str | None = Field(default=None, max_length=40)
    fecha_ingreso: date | None = None
    fecha_nacimiento: date | None = None
    observaciones: str | None = None
    activo: bool | None = None


class PersonaSalida(EsquemaBase):
    id: UUID
    cedula: str
    nombres: str
    apellidos: str
    nombre_completo: str
    email_institucional: str | None
    email_personal: str | None
    telefono: str | None
    tipo_vinculacion: TipoVinculacion
    unidad: str | None
    cargo: str | None
    codigo_empleado: str | None
    fecha_ingreso: date | None
    activo: bool
    observaciones: str | None
    titulos_registrados: int
    total_consultas: int
    ultima_consulta_en: datetime | None
    ultima_consulta_estado: EstadoConsulta | None
    ultima_consulta_exitosa_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime

    @classmethod
    def desde(cls, p: Persona) -> PersonaSalida:
        return cls(
            id=p.id,
            cedula=p.cedula.valor,
            nombres=p.nombre.nombres,
            apellidos=p.nombre.apellidos,
            nombre_completo=p.nombre.completo,
            email_institucional=str(p.email_institucional) if p.email_institucional else None,
            email_personal=str(p.email_personal) if p.email_personal else None,
            telefono=p.telefono,
            tipo_vinculacion=p.tipo_vinculacion,
            unidad=p.unidad,
            cargo=p.cargo,
            codigo_empleado=p.codigo_empleado,
            fecha_ingreso=p.fecha_ingreso,
            activo=p.activo,
            observaciones=p.observaciones,
            titulos_registrados=p.titulos_registrados,
            total_consultas=p.total_consultas,
            ultima_consulta_en=p.ultima_consulta_en,
            ultima_consulta_estado=p.ultima_consulta_estado,
            ultima_consulta_exitosa_en=p.ultima_consulta_exitosa_en,
            creado_en=p.creado_en,
            actualizado_en=p.actualizado_en,
        )


class FilaImportacionEntrada(EsquemaBase):
    cedula: str
    nombres: str
    apellidos: str
    email_institucional: str | None = None
    tipo_vinculacion: str | None = None
    unidad: str | None = None
    cargo: str | None = None
    codigo_empleado: str | None = None


class ErrorImportacionSalida(EsquemaBase):
    fila: int
    cedula: str
    motivo: str


class ResultadoImportacionSalida(EsquemaBase):
    total_filas: int
    creadas: int
    duplicadas: int
    rechazadas: list[ErrorImportacionSalida]
    exitosa: bool


# ===========================================================================
# Titulos
# ===========================================================================


class TituloCrear(EsquemaBase):
    persona_id: UUID
    denominacion: Annotated[str, Field(min_length=3, max_length=400)]
    institucion: Annotated[str, Field(min_length=2, max_length=300)]
    nivel: NivelTitulo | None = None
    numero_registro: str | None = Field(default=None, max_length=64)
    fecha_registro: date | None = None
    fecha_graduacion: date | None = None
    area_conocimiento: str | None = Field(default=None, max_length=200)
    pais: str = "ECUADOR"
    observacion_registro: str | None = None


class TituloActualizar(EsquemaBase):
    denominacion: str | None = Field(default=None, max_length=400)
    institucion: str | None = Field(default=None, max_length=300)
    nivel: NivelTitulo | None = None
    numero_registro: str | None = Field(default=None, max_length=64)
    fecha_registro: date | None = None
    fecha_graduacion: date | None = None
    area_conocimiento: str | None = Field(default=None, max_length=200)
    observacion_registro: str | None = None


class TituloSalida(EsquemaBase):
    id: UUID
    persona_id: UUID
    denominacion: str
    institucion: str
    nivel: NivelTitulo
    numero_registro: str | None
    fecha_registro: date | None
    fecha_graduacion: date | None
    area_conocimiento: str | None
    pais: str
    observacion_registro: str | None
    origen: OrigenTitulo
    estado: EstadoTitulo
    es_posgrado: bool
    requiere_atencion: bool
    verificado: bool
    verificado_en: datetime | None
    visto_primera_vez_en: datetime
    visto_ultima_vez_en: datetime
    retirado_en: datetime | None

    @classmethod
    def desde(cls, t: Titulo) -> TituloSalida:
        return cls(
            id=t.id,
            persona_id=t.persona_id,
            denominacion=t.denominacion,
            institucion=t.institucion,
            nivel=t.nivel,
            numero_registro=t.numero_registro,
            fecha_registro=t.fecha_registro,
            fecha_graduacion=t.fecha_graduacion,
            area_conocimiento=t.area_conocimiento,
            pais=t.pais,
            observacion_registro=t.observacion_registro,
            origen=t.origen,
            estado=t.estado,
            es_posgrado=t.es_posgrado,
            requiere_atencion=t.requiere_atencion,
            verificado=t.verificado,
            verificado_en=t.verificado_en,
            visto_primera_vez_en=t.visto_primera_vez_en,
            visto_ultima_vez_en=t.visto_ultima_vez_en,
            retirado_en=t.retirado_en,
        )


class PersonaDetalleSalida(EsquemaBase):
    persona: PersonaSalida
    titulos: list[TituloSalida]
    total_titulos: int
    titulos_vigentes: int

    @classmethod
    def desde(cls, detalle: PersonaConTitulos) -> PersonaDetalleSalida:
        return cls(
            persona=PersonaSalida.desde(detalle.persona),
            titulos=[TituloSalida.desde(t) for t in detalle.titulos],
            total_titulos=detalle.total_titulos,
            titulos_vigentes=detalle.titulos_vigentes,
        )


# ===========================================================================
# Consultas
# ===========================================================================


class CambioSalida(EsquemaBase):
    tipo: str
    titulo_id: UUID | None
    denominacion: str
    detalle: dict[str, Any]


class ConsultaLogSalida(EsquemaBase):
    id: UUID
    persona_id: UUID
    cedula: str
    estado: EstadoConsulta
    job_id: UUID | None
    proveedor: str
    intento: int
    iniciado_en: datetime
    finalizado_en: datetime | None
    duracion_ms: int | None
    titulos_encontrados: int
    titulos_nuevos: int
    titulos_actualizados: int
    titulos_retirados: int
    hubo_cambios: bool
    resumen: str
    mensaje: str | None
    tipo_error: str | None
    codigo_http: int | None
    cambios: list[CambioSalida]
    desafio_id: str | None = Field(
        default=None,
        description=(
            "Identificador del desafio pendiente. Solo viene informado cuando el "
            "estado es DESAFIO_PENDIENTE; permite resolverlo desde la interfaz."
        ),
    )

    @classmethod
    def desde(cls, log: ConsultaLog) -> ConsultaLogSalida:
        return cls(
            id=log.id,
            persona_id=log.persona_id,
            cedula=log.cedula.valor,
            estado=log.estado,
            job_id=log.job_id,
            proveedor=log.proveedor,
            intento=log.intento,
            iniciado_en=log.iniciado_en,
            finalizado_en=log.finalizado_en,
            duracion_ms=log.duracion_ms,
            titulos_encontrados=log.titulos_encontrados,
            titulos_nuevos=log.titulos_nuevos,
            titulos_actualizados=log.titulos_actualizados,
            titulos_retirados=log.titulos_retirados,
            hubo_cambios=log.hubo_cambios,
            resumen=log.resumen,
            mensaje=log.mensaje,
            tipo_error=log.tipo_error,
            codigo_http=log.codigo_http,
            cambios=[
                CambioSalida(
                    tipo=c.tipo.value,
                    titulo_id=c.titulo_id,
                    denominacion=c.denominacion,
                    detalle=c.detalle,
                )
                for c in log.cambios
            ],
            desafio_id=cls._desafio_de(log),
        )

    @staticmethod
    def _desafio_de(log: ConsultaLog) -> str | None:
        """Extrae el identificador del desafio de la respuesta cruda.

        Solo se expone para los registros que estan esperando resolucion: en
        cualquier otro caso, `respuesta_cruda` contiene datos del proveedor que
        no deben salir de la base.
        """
        if log.estado is not EstadoConsulta.DESAFIO_PENDIENTE:
            return None
        crudo = log.respuesta_cruda or {}
        valor = crudo.get("desafio_id")
        return str(valor) if valor else None


class ResultadoConsultaSalida(EsquemaBase):
    log: ConsultaLogSalida
    requiere_intervencion: bool
    desafio_id: str | None
    resumen_cambios: dict[str, int]

    @classmethod
    def desde(cls, resultado: ResultadoEjecucion) -> ResultadoConsultaSalida:
        return cls(
            log=ConsultaLogSalida.desde(resultado.log),
            requiere_intervencion=resultado.requiere_intervencion,
            desafio_id=resultado.desafio_id,
            resumen_cambios=resultado.resumen_cambios,
        )


class JobCrear(EsquemaBase):
    nombre: Annotated[str, Field(min_length=3, max_length=160)]
    periodo_dias: int | None = Field(
        default=None,
        ge=1,
        le=730,
        description="Duracion del periodo de cobertura. Por defecto, el configurado.",
    )
    limite_personas: int | None = Field(
        default=None,
        ge=1,
        description="Acota el job a las N personas mas prioritarias",
    )
    iniciar_inmediatamente: bool = False
    distribuir_en_periodo: bool = Field(
        default=False,
        description=(
            "Reparte las consultas de forma uniforme durante todo el periodo. "
            "Por defecto el ritmo lo impone la politica de planificacion."
        ),
    )


class JobSalida(EsquemaBase):
    id: UUID
    nombre: str
    estado: EstadoJob
    periodo_inicio: datetime
    periodo_fin: datetime
    total_items: int
    completados: int
    fallidos: int
    omitidos: int
    esperando_desafio: int
    pendientes: int
    porcentaje_avance: float
    esta_cubierto: bool
    fallos_consecutivos: int
    pausado_automaticamente: bool
    motivo_pausa: str | None
    ritmo_requerido_por_hora: float
    iniciado_en: datetime | None
    finalizado_en: datetime | None
    ultima_actividad_en: datetime | None
    configuracion: dict[str, Any]

    @classmethod
    def desde(cls, job: JobCobertura) -> JobSalida:
        from app.domain.value_objects import ahora_utc

        return cls(
            id=job.id,
            nombre=job.nombre,
            estado=job.estado,
            periodo_inicio=job.periodo.inicio,
            periodo_fin=job.periodo.fin,
            total_items=job.total_items,
            completados=job.completados,
            fallidos=job.fallidos,
            omitidos=job.omitidos,
            esperando_desafio=job.esperando_desafio,
            pendientes=job.pendientes,
            porcentaje_avance=job.porcentaje_avance,
            esta_cubierto=job.esta_cubierto,
            fallos_consecutivos=job.fallos_consecutivos,
            pausado_automaticamente=job.pausado_automaticamente,
            motivo_pausa=job.motivo_pausa,
            ritmo_requerido_por_hora=job.ritmo_requerido_por_hora(ahora_utc()),
            iniciado_en=job.iniciado_en,
            finalizado_en=job.finalizado_en,
            ultima_actividad_en=job.ultima_actividad_en,
            configuracion=job.configuracion,
        )


class JobCreadoSalida(EsquemaBase):
    job: JobSalida
    factible: bool
    consultas_diarias_estimadas: int
    dias_necesarios: int
    advertencia: str | None


class ControlJobEntrada(EsquemaBase):
    accion: str = Field(description="iniciar | pausar | reanudar | cancelar")
    motivo: str | None = None


class ResolverDesafioEntrada(EsquemaBase):
    desafio_id: Annotated[str, Field(min_length=1, max_length=128)]
    respuesta: Annotated[str, Field(min_length=1, max_length=64)]


class DesafioPendienteSalida(EsquemaBase):
    """Desafio a la espera de resolucion humana.

    `cedula` va enmascarada: el operador que transcribe un codigo no necesita
    ver el documento completo de la persona.
    """

    desafio_id: str
    persona_id: UUID
    cedula_enmascarada: str
    nombre_persona: str
    tipo: str
    imagen_base64: str | None
    instruccion: str
    expira_en_segundos: int


# ===========================================================================
# Reportes y tablero
# ===========================================================================


class PeticionReporte(EsquemaBase):
    formato: FormatoReporte = FormatoReporte.XLSX


class ConteoSalida(EsquemaBase):
    etiqueta: str
    valor: int
    porcentaje: float


class PuntoSerieSalida(EsquemaBase):
    fecha: date
    valor: int


def _conteo(c: Any) -> dict[str, Any]:
    """Serializa un `ConteoEtiquetado`.

    Se hace campo a campo porque los objetos de analitica usan `slots` y no
    exponen `__dict__`.
    """
    return {"etiqueta": c.etiqueta, "valor": c.valor, "porcentaje": c.porcentaje}


class TableroSalida(EsquemaBase):
    cobertura: dict[str, Any]
    titulos: dict[str, Any]
    consultas: dict[str, Any]
    personas_por_unidad: list[ConteoSalida]
    personas_por_vinculacion: list[ConteoSalida]
    generado_en: str

    @classmethod
    def desde(cls, tablero: TableroCompleto) -> TableroSalida:
        cob, tit, con = tablero.cobertura, tablero.titulos, tablero.consultas
        return cls(
            cobertura={
                "total_personas": cob.total_personas,
                "personas_activas": cob.personas_activas,
                "con_titulos": cob.con_titulos,
                "sin_titulos": cob.sin_titulos,
                "nunca_consultadas": cob.nunca_consultadas,
                "consultadas_en_periodo": cob.consultadas_en_periodo,
                "con_error_ultima_consulta": cob.con_error_ultima_consulta,
                "porcentaje_cobertura": cob.porcentaje_cobertura,
                "porcentaje_con_titulos": cob.porcentaje_con_titulos,
            },
            titulos={
                "total": tit.total,
                "vigentes": tit.vigentes,
                "retirados": tit.retirados,
                "por_verificar": tit.por_verificar,
                "verificados": tit.verificados,
                "posgrados": tit.posgrados,
                "por_nivel": [_conteo(c) for c in tit.por_nivel],
                "por_institucion": [_conteo(c) for c in tit.por_institucion],
            },
            consultas={
                "total_periodo": con.total_periodo,
                "exitosas": con.exitosas,
                "sin_datos": con.sin_datos,
                "con_error": con.con_error,
                "esperando_desafio": con.esperando_desafio,
                "con_cambios": con.con_cambios,
                "duracion_promedio_ms": con.duracion_promedio_ms,
                "tasa_exito": con.tasa_exito,
                "por_estado": [_conteo(c) for c in con.por_estado],
                "tendencia_diaria": [
                    {"fecha": p.fecha.isoformat(), "valor": p.valor} for p in con.tendencia_diaria
                ],
            },
            personas_por_unidad=[
                ConteoSalida(etiqueta=c.etiqueta, valor=c.valor, porcentaje=c.porcentaje)
                for c in tablero.personas_por_unidad
            ],
            personas_por_vinculacion=[
                ConteoSalida(etiqueta=c.etiqueta, valor=c.valor, porcentaje=c.porcentaje)
                for c in tablero.personas_por_vinculacion
            ],
            generado_en=tablero.generado_en,
        )


# ===========================================================================
# Usuarios y roles
# ===========================================================================


class UsuarioCrear(EsquemaBase):
    email: Annotated[str, Field(max_length=254)]
    nombre_completo: Annotated[str, Field(min_length=3, max_length=200)]
    contrasena: str | None = Field(default=None, min_length=10, max_length=128)
    roles: list[str] = Field(min_length=1)
    activo: bool = True
    debe_cambiar_contrasena: bool = True


class UsuarioActualizar(EsquemaBase):
    nombre_completo: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    activo: bool | None = None
    roles: list[str] | None = None


class RestablecerContrasenaEntrada(EsquemaBase):
    contrasena_nueva: Annotated[str, Field(min_length=10, max_length=128)]
    forzar_cambio: bool = True


class RolSalida(EsquemaBase):
    id: UUID
    codigo: str
    nombre: str
    descripcion: str
    es_sistema: bool
    permisos: list[str]

    @classmethod
    def desde(cls, rol: Any) -> RolSalida:
        return cls(
            id=rol.id,
            codigo=rol.codigo,
            nombre=rol.nombre,
            descripcion=rol.descripcion,
            es_sistema=rol.es_sistema,
            permisos=sorted(p.value for p in rol.permisos),
        )


class RolActualizar(EsquemaBase):
    nombre: str | None = Field(default=None, max_length=64)
    descripcion: str | None = None
    permisos: list[str] | None = None


class PermisoSalida(EsquemaBase):
    codigo: str
    modulo: str
    accion: str
