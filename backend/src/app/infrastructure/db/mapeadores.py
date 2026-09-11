"""Traduccion entre modelos ORM y entidades de dominio.

Esta capa es el precio de mantener el dominio limpio, y vale la pena: sin ella,
cada campo que se agregue a la base se filtra hasta las reglas de negocio. Aqui
el cambio queda contenido en una funcion.

Convencion: `a_dominio(modelo)` lee, `a_modelo(entidad, modelo?)` escribe. La
segunda acepta un modelo existente para actualizarlo en sitio y conservar el
seguimiento de cambios de la sesion de SQLAlchemy.
"""

from __future__ import annotations

from typing import Any

from app.domain.entities.auth import PermisoEntidad, Rol, TokenRefresco, Usuario
from app.domain.entities.consulta import (
    CambioDetectado,
    ConsultaLog,
    ItemJob,
    JobCobertura,
)
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import (
    AuthProvider,
    EstadoConsulta,
    EstadoItemJob,
    EstadoJob,
    EstadoTitulo,
    NivelTitulo,
    OrigenTitulo,
    Permiso,
    TipoCambio,
    TipoDocumento,
    TipoVinculacion,
)
from app.domain.value_objects import Cedula, Email, NombrePersona, PeriodoCobertura
from app.infrastructure.db.modelos import (
    ConsultaLogModel,
    ItemJobModel,
    JobCoberturaModel,
    PermisoModel,
    PersonaModel,
    RolModel,
    TituloModel,
    TokenRefrescoModel,
    UsuarioModel,
)


def _enum(tipo: type, valor: str | None, por_defecto: Any) -> Any:
    """Convierte texto a enumeracion tolerando valores desconocidos.

    Un valor invalido en la base —por una migracion a medias o una escritura
    manual— no debe tumbar la lectura de toda la fila.
    """
    if valor is None:
        return por_defecto
    try:
        return tipo(valor)
    except ValueError:
        return por_defecto


# ===========================================================================
# Identidad
# ===========================================================================


def permiso_a_dominio(modelo: PermisoModel) -> PermisoEntidad:
    return PermisoEntidad(
        codigo=Permiso(modelo.codigo),
        nombre=modelo.nombre,
        descripcion=modelo.descripcion,
        modulo=modelo.modulo,
        id=modelo.id,
    )


def rol_a_dominio(modelo: RolModel) -> Rol:
    permisos: set[Permiso] = set()
    for p in modelo.permisos:
        try:
            permisos.add(Permiso(p.codigo))
        except ValueError:
            continue  # permiso retirado del catalogo: se ignora
    return Rol(
        id=modelo.id,
        codigo=modelo.codigo,
        nombre=modelo.nombre,
        descripcion=modelo.descripcion,
        permisos=permisos,
        es_sistema=modelo.es_sistema,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def rol_a_modelo(entidad: Rol, modelo: RolModel | None = None) -> RolModel:
    modelo = modelo or RolModel(id=entidad.id)
    modelo.codigo = entidad.codigo
    modelo.nombre = entidad.nombre
    modelo.descripcion = entidad.descripcion
    modelo.es_sistema = entidad.es_sistema
    return modelo


def usuario_a_dominio(modelo: UsuarioModel) -> Usuario:
    return Usuario(
        id=modelo.id,
        email=Email(modelo.email),
        nombre_completo=modelo.nombre_completo,
        proveedor=_enum(AuthProvider, modelo.proveedor, AuthProvider.LOCAL),
        hash_contrasena=modelo.hash_contrasena,
        identificador_externo=modelo.identificador_externo,
        roles={rol_a_dominio(r) for r in modelo.roles},
        activo=modelo.activo,
        es_superusuario=modelo.es_superusuario,
        debe_cambiar_contrasena=modelo.debe_cambiar_contrasena,
        intentos_fallidos=modelo.intentos_fallidos,
        bloqueado_hasta=modelo.bloqueado_hasta,
        ultimo_acceso=modelo.ultimo_acceso,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def usuario_a_modelo(entidad: Usuario, modelo: UsuarioModel | None = None) -> UsuarioModel:
    modelo = modelo or UsuarioModel(id=entidad.id)
    modelo.email = entidad.email.valor
    modelo.nombre_completo = entidad.nombre_completo
    modelo.proveedor = entidad.proveedor.value
    modelo.hash_contrasena = entidad.hash_contrasena
    modelo.identificador_externo = entidad.identificador_externo
    modelo.activo = entidad.activo
    modelo.es_superusuario = entidad.es_superusuario
    modelo.debe_cambiar_contrasena = entidad.debe_cambiar_contrasena
    modelo.intentos_fallidos = entidad.intentos_fallidos
    modelo.bloqueado_hasta = entidad.bloqueado_hasta
    modelo.ultimo_acceso = entidad.ultimo_acceso
    return modelo


def token_a_dominio(modelo: TokenRefrescoModel) -> TokenRefresco:
    return TokenRefresco(
        id=modelo.id,
        usuario_id=modelo.usuario_id,
        hash_token=modelo.hash_token,
        expira_en=modelo.expira_en,
        creado_en=modelo.creado_en,
        revocado_en=modelo.revocado_en,
        reemplazado_por=modelo.reemplazado_por,
        user_agent=modelo.user_agent,
        direccion_ip=modelo.direccion_ip,
    )


def token_a_modelo(
    entidad: TokenRefresco, modelo: TokenRefrescoModel | None = None
) -> TokenRefrescoModel:
    modelo = modelo or TokenRefrescoModel(id=entidad.id)
    modelo.usuario_id = entidad.usuario_id
    modelo.hash_token = entidad.hash_token
    modelo.expira_en = entidad.expira_en
    modelo.revocado_en = entidad.revocado_en
    modelo.reemplazado_por = entidad.reemplazado_por
    modelo.user_agent = entidad.user_agent
    modelo.direccion_ip = entidad.direccion_ip
    return modelo


# ===========================================================================
# Personas y titulos
# ===========================================================================


def persona_a_dominio(modelo: PersonaModel) -> Persona:
    return Persona(
        id=modelo.id,
        cedula=Cedula(modelo.cedula),
        nombre=NombrePersona(nombres=modelo.nombres, apellidos=modelo.apellidos),
        tipo_documento=_enum(TipoDocumento, modelo.tipo_documento, TipoDocumento.CEDULA),
        email_institucional=Email(modelo.email_institucional)
        if modelo.email_institucional
        else None,
        email_personal=Email(modelo.email_personal) if modelo.email_personal else None,
        telefono=modelo.telefono,
        tipo_vinculacion=_enum(TipoVinculacion, modelo.tipo_vinculacion, TipoVinculacion.OTRO),
        unidad=modelo.unidad,
        cargo=modelo.cargo,
        codigo_empleado=modelo.codigo_empleado,
        fecha_ingreso=modelo.fecha_ingreso,
        fecha_nacimiento=modelo.fecha_nacimiento,
        activo=modelo.activo,
        observaciones=modelo.observaciones,
        ultima_consulta_en=modelo.ultima_consulta_en,
        ultima_consulta_estado=_enum(EstadoConsulta, modelo.ultima_consulta_estado, None),
        ultima_consulta_exitosa_en=modelo.ultima_consulta_exitosa_en,
        total_consultas=modelo.total_consultas,
        titulos_registrados=modelo.titulos_registrados,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
        creado_por=modelo.creado_por,
    )


def persona_a_modelo(entidad: Persona, modelo: PersonaModel | None = None) -> PersonaModel:
    modelo = modelo or PersonaModel(id=entidad.id)
    modelo.cedula = entidad.cedula.valor
    modelo.tipo_documento = entidad.tipo_documento.value
    modelo.nombres = entidad.nombre.nombres
    modelo.apellidos = entidad.nombre.apellidos
    modelo.clave_busqueda = entidad.clave_busqueda
    modelo.email_institucional = (
        entidad.email_institucional.valor if entidad.email_institucional else None
    )
    modelo.email_personal = entidad.email_personal.valor if entidad.email_personal else None
    modelo.telefono = entidad.telefono
    modelo.tipo_vinculacion = entidad.tipo_vinculacion.value
    modelo.unidad = entidad.unidad
    modelo.cargo = entidad.cargo
    modelo.codigo_empleado = entidad.codigo_empleado
    modelo.fecha_ingreso = entidad.fecha_ingreso
    modelo.fecha_nacimiento = entidad.fecha_nacimiento
    modelo.activo = entidad.activo
    modelo.observaciones = entidad.observaciones
    modelo.ultima_consulta_en = entidad.ultima_consulta_en
    modelo.ultima_consulta_estado = (
        entidad.ultima_consulta_estado.value if entidad.ultima_consulta_estado else None
    )
    modelo.ultima_consulta_exitosa_en = entidad.ultima_consulta_exitosa_en
    modelo.total_consultas = entidad.total_consultas
    modelo.titulos_registrados = entidad.titulos_registrados
    modelo.creado_por = entidad.creado_por
    return modelo


def titulo_a_dominio(modelo: TituloModel) -> Titulo:
    return Titulo(
        id=modelo.id,
        persona_id=modelo.persona_id,
        denominacion=modelo.denominacion,
        institucion=modelo.institucion,
        nivel=_enum(NivelTitulo, modelo.nivel, NivelTitulo.NO_DETERMINADO),
        numero_registro=modelo.numero_registro,
        fecha_registro=modelo.fecha_registro,
        fecha_graduacion=modelo.fecha_graduacion,
        area_conocimiento=modelo.area_conocimiento,
        pais=modelo.pais,
        observacion_registro=modelo.observacion_registro,
        origen=_enum(OrigenTitulo, modelo.origen, OrigenTitulo.SENESCYT),
        estado=_enum(EstadoTitulo, modelo.estado, EstadoTitulo.VIGENTE),
        huella=modelo.huella,
        datos_crudos=dict(modelo.datos_crudos or {}),
        visto_primera_vez_en=modelo.visto_primera_vez_en,
        visto_ultima_vez_en=modelo.visto_ultima_vez_en,
        retirado_en=modelo.retirado_en,
        verificado=modelo.verificado,
        verificado_por=modelo.verificado_por,
        verificado_en=modelo.verificado_en,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def titulo_a_modelo(entidad: Titulo, modelo: TituloModel | None = None) -> TituloModel:
    modelo = modelo or TituloModel(id=entidad.id)
    modelo.persona_id = entidad.persona_id
    modelo.denominacion = entidad.denominacion
    modelo.institucion = entidad.institucion
    modelo.nivel = entidad.nivel.value
    modelo.numero_registro = entidad.numero_registro
    modelo.fecha_registro = entidad.fecha_registro
    modelo.fecha_graduacion = entidad.fecha_graduacion
    modelo.area_conocimiento = entidad.area_conocimiento
    modelo.pais = entidad.pais
    modelo.observacion_registro = entidad.observacion_registro
    modelo.origen = entidad.origen.value
    modelo.estado = entidad.estado.value
    modelo.huella = entidad.huella
    modelo.datos_crudos = entidad.datos_crudos
    modelo.visto_primera_vez_en = entidad.visto_primera_vez_en
    modelo.visto_ultima_vez_en = entidad.visto_ultima_vez_en
    modelo.retirado_en = entidad.retirado_en
    modelo.verificado = entidad.verificado
    modelo.verificado_por = entidad.verificado_por
    modelo.verificado_en = entidad.verificado_en
    return modelo


# ===========================================================================
# Consultas
# ===========================================================================


def log_a_dominio(modelo: ConsultaLogModel) -> ConsultaLog:
    return ConsultaLog(
        id=modelo.id,
        persona_id=modelo.persona_id,
        cedula=Cedula(modelo.cedula),
        estado=_enum(EstadoConsulta, modelo.estado, EstadoConsulta.ERROR_PROVEEDOR),
        job_id=modelo.job_id,
        proveedor=modelo.proveedor,
        intento=modelo.intento,
        iniciado_en=modelo.iniciado_en,
        finalizado_en=modelo.finalizado_en,
        duracion_ms=modelo.duracion_ms,
        titulos_encontrados=modelo.titulos_encontrados,
        titulos_nuevos=modelo.titulos_nuevos,
        titulos_actualizados=modelo.titulos_actualizados,
        titulos_retirados=modelo.titulos_retirados,
        cambios=[_cambio_a_dominio(c) for c in (modelo.cambios or [])],
        mensaje=modelo.mensaje,
        tipo_error=modelo.tipo_error,
        codigo_http=modelo.codigo_http,
        respuesta_cruda=modelo.respuesta_cruda,
        ejecutado_por=modelo.ejecutado_por,
    )


def _cambio_a_dominio(crudo: dict[str, Any]) -> CambioDetectado:
    from uuid import UUID

    titulo_id = crudo.get("titulo_id")
    return CambioDetectado(
        tipo=_enum(TipoCambio, crudo.get("tipo"), TipoCambio.SIN_CAMBIOS),
        titulo_id=UUID(titulo_id) if titulo_id else None,
        denominacion=crudo.get("denominacion", ""),
        detalle=crudo.get("detalle", {}),
    )


def log_a_modelo(entidad: ConsultaLog, modelo: ConsultaLogModel | None = None) -> ConsultaLogModel:
    modelo = modelo or ConsultaLogModel(id=entidad.id)
    modelo.persona_id = entidad.persona_id
    modelo.cedula = entidad.cedula.valor
    modelo.estado = entidad.estado.value
    modelo.job_id = entidad.job_id
    modelo.proveedor = entidad.proveedor
    modelo.intento = entidad.intento
    modelo.iniciado_en = entidad.iniciado_en
    modelo.finalizado_en = entidad.finalizado_en
    modelo.duracion_ms = entidad.duracion_ms
    modelo.titulos_encontrados = entidad.titulos_encontrados
    modelo.titulos_nuevos = entidad.titulos_nuevos
    modelo.titulos_actualizados = entidad.titulos_actualizados
    modelo.titulos_retirados = entidad.titulos_retirados
    modelo.cambios = [c.a_dict() for c in entidad.cambios]
    modelo.mensaje = entidad.mensaje
    modelo.tipo_error = entidad.tipo_error
    modelo.codigo_http = entidad.codigo_http
    modelo.respuesta_cruda = entidad.respuesta_cruda
    modelo.ejecutado_por = entidad.ejecutado_por
    return modelo


def job_a_dominio(modelo: JobCoberturaModel) -> JobCobertura:
    return JobCobertura(
        id=modelo.id,
        nombre=modelo.nombre,
        periodo=PeriodoCobertura(inicio=modelo.periodo_inicio, fin=modelo.periodo_fin),
        estado=_enum(EstadoJob, modelo.estado, EstadoJob.BORRADOR),
        total_items=modelo.total_items,
        completados=modelo.completados,
        fallidos=modelo.fallidos,
        omitidos=modelo.omitidos,
        esperando_desafio=modelo.esperando_desafio,
        fallos_consecutivos=modelo.fallos_consecutivos,
        pausado_automaticamente=modelo.pausado_automaticamente,
        motivo_pausa=modelo.motivo_pausa,
        proxima_ejecucion_en=modelo.proxima_ejecucion_en,
        ultima_actividad_en=modelo.ultima_actividad_en,
        iniciado_en=modelo.iniciado_en,
        finalizado_en=modelo.finalizado_en,
        configuracion=dict(modelo.configuracion or {}),
        creado_por=modelo.creado_por,
        creado_en=modelo.creado_en,
    )


def job_a_modelo(
    entidad: JobCobertura, modelo: JobCoberturaModel | None = None
) -> JobCoberturaModel:
    modelo = modelo or JobCoberturaModel(id=entidad.id)
    modelo.nombre = entidad.nombre
    modelo.estado = entidad.estado.value
    modelo.periodo_inicio = entidad.periodo.inicio
    modelo.periodo_fin = entidad.periodo.fin
    modelo.total_items = entidad.total_items
    modelo.completados = entidad.completados
    modelo.fallidos = entidad.fallidos
    modelo.omitidos = entidad.omitidos
    modelo.esperando_desafio = entidad.esperando_desafio
    modelo.fallos_consecutivos = entidad.fallos_consecutivos
    modelo.pausado_automaticamente = entidad.pausado_automaticamente
    modelo.motivo_pausa = entidad.motivo_pausa
    modelo.proxima_ejecucion_en = entidad.proxima_ejecucion_en
    modelo.ultima_actividad_en = entidad.ultima_actividad_en
    modelo.iniciado_en = entidad.iniciado_en
    modelo.finalizado_en = entidad.finalizado_en
    modelo.configuracion = entidad.configuracion
    modelo.creado_por = entidad.creado_por
    return modelo


def item_a_dominio(modelo: ItemJobModel) -> ItemJob:
    return ItemJob(
        id=modelo.id,
        job_id=modelo.job_id,
        persona_id=modelo.persona_id,
        orden=modelo.orden,
        estado=_enum(EstadoItemJob, modelo.estado, EstadoItemJob.PENDIENTE),
        programado_para=modelo.programado_para,
        intentos=modelo.intentos,
        ultimo_log_id=modelo.ultimo_log_id,
        ultimo_error=modelo.ultimo_error,
        desafio_id=modelo.desafio_id,
        procesado_en=modelo.procesado_en,
    )


def item_a_modelo(entidad: ItemJob, modelo: ItemJobModel | None = None) -> ItemJobModel:
    modelo = modelo or ItemJobModel(id=entidad.id)
    modelo.job_id = entidad.job_id
    modelo.persona_id = entidad.persona_id
    modelo.orden = entidad.orden
    modelo.estado = entidad.estado.value
    modelo.programado_para = entidad.programado_para
    modelo.intentos = entidad.intentos
    modelo.ultimo_log_id = entidad.ultimo_log_id
    modelo.ultimo_error = entidad.ultimo_error
    modelo.desafio_id = entidad.desafio_id
    modelo.procesado_en = entidad.procesado_en
    return modelo
