"""Traduccion entre los modelos ORM de la matricula estudiantil y el dominio."""

from __future__ import annotations

from app.domain.entities.estudiantes import BecaEstudiante, Estudiante, MatriculaEstudiante
from app.infrastructure.db.modelos_estudiantes import (
    BecaEstudianteModel,
    EstudianteModel,
    MatriculaEstudianteModel,
)

# ---------------------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------------------


def estudiante_a_dominio(modelo: EstudianteModel) -> Estudiante:
    return Estudiante(
        id=modelo.id,
        cedula=modelo.cedula,
        id_banner=modelo.id_banner,
        nombre=modelo.nombre,
        genero_id=modelo.genero_id,
        mail_personal=modelo.mail_personal,
        mail_ute=modelo.mail_ute,
        telefono_celular=modelo.telefono_celular,
        telefono_fijo=modelo.telefono_fijo,
        fecha_nacimiento=modelo.fecha_nacimiento,
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def estudiante_a_modelo(
    entidad: Estudiante, modelo: EstudianteModel | None = None
) -> EstudianteModel:
    modelo = modelo or EstudianteModel(id=entidad.id)
    modelo.cedula = entidad.cedula
    modelo.id_banner = entidad.id_banner
    modelo.nombre = entidad.nombre
    modelo.genero_id = entidad.genero_id
    modelo.mail_personal = entidad.mail_personal
    modelo.mail_ute = entidad.mail_ute
    modelo.telefono_celular = entidad.telefono_celular
    modelo.telefono_fijo = entidad.telefono_fijo
    modelo.fecha_nacimiento = entidad.fecha_nacimiento
    return modelo


# ---------------------------------------------------------------------------
# Matriculas y becas
# ---------------------------------------------------------------------------


def beca_a_dominio(modelo: BecaEstudianteModel) -> BecaEstudiante:
    return BecaEstudiante(
        id=modelo.id,
        codigo_beca=modelo.codigo_beca,
        financiamiento=modelo.financiamiento,
        tipo_beca=modelo.tipo_beca,
        porcentaje=modelo.porcentaje,
    )


def matricula_a_dominio(modelo: MatriculaEstudianteModel) -> MatriculaEstudiante:
    return MatriculaEstudiante(
        id=modelo.id,
        estudiante_id=modelo.estudiante_id,
        periodo=modelo.periodo,
        sede=modelo.sede,
        facultad=modelo.facultad,
        carrera=modelo.carrera,
        carrera_id=modelo.carrera_id,
        tipo_carrera=modelo.tipo_carrera,
        modalidad=modelo.modalidad,
        nivel_formacion_1=modelo.nivel_formacion_1,
        nivel_formacion_2=modelo.nivel_formacion_2,
        tipo_estudiante=modelo.tipo_estudiante,
        sistema=modelo.sistema,
        matriculado=modelo.matriculado,
        solicitud_retiro=modelo.solicitud_retiro,
        bloqueo_plataforma=bool(modelo.bloqueo_plataforma),
        estado=modelo.estado,
        becas=[beca_a_dominio(b) for b in modelo.becas],
        creado_en=modelo.creado_en,
        actualizado_en=modelo.actualizado_en,
    )


def matricula_a_modelo(
    entidad: MatriculaEstudiante, modelo: MatriculaEstudianteModel | None = None
) -> MatriculaEstudianteModel:
    """No copia `becas`: el repositorio las reemplaza aparte, igual que el
    distributivo hace con sus asignaturas."""
    modelo = modelo or MatriculaEstudianteModel(id=entidad.id)
    modelo.estudiante_id = entidad.estudiante_id
    modelo.periodo = entidad.periodo
    modelo.sede = entidad.sede
    modelo.facultad = entidad.facultad
    modelo.carrera = entidad.carrera
    modelo.carrera_id = entidad.carrera_id
    modelo.tipo_carrera = entidad.tipo_carrera
    modelo.modalidad = entidad.modalidad
    modelo.nivel_formacion_1 = entidad.nivel_formacion_1
    modelo.nivel_formacion_2 = entidad.nivel_formacion_2
    modelo.tipo_estudiante = entidad.tipo_estudiante
    modelo.sistema = entidad.sistema
    modelo.matriculado = entidad.matriculado
    modelo.solicitud_retiro = entidad.solicitud_retiro
    modelo.bloqueo_plataforma = entidad.bloqueo_plataforma
    modelo.estado = entidad.estado
    return modelo
