/** Entidades del dominio. Reflejan las del backend. */

import type {
  AuthProvider,
  EstadoConsulta,
  EstadoJob,
  EstadoTitulo,
  NivelTitulo,
  OrigenTitulo,
  Permiso,
  TipoVinculacion,
} from './enums';

// ---------------------------------------------------------------------------
// Identidad y acceso
// ---------------------------------------------------------------------------

export interface Rol {
  readonly id: string;
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion: string;
  readonly esSistema: boolean;
  readonly permisos: readonly Permiso[];
}

export interface RolResumen {
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion: string;
  readonly esSistema: boolean;
}

export interface Usuario {
  readonly id: string;
  readonly email: string;
  readonly nombreCompleto: string;
  readonly proveedor: AuthProvider;
  readonly activo: boolean;
  readonly esSuperusuario: boolean;
  readonly debeCambiarContrasena: boolean;
  readonly roles: readonly RolResumen[];
  /** Permisos efectivos: la union de los de todos sus roles. */
  readonly permisos: readonly Permiso[];

  /** Facultades que puede consultar. Vacia no restringe nada. */
  readonly facultadesIds: readonly string[];
  /** Carreras que puede consultar. Vacia no restringe nada. */
  readonly carrerasIds: readonly string[];
  /** `true` si la cuenta ve el distributivo completo. */
  readonly alcanceTotal: boolean;

  readonly ultimoAcceso: string | null;
  readonly creadoEn: string;
}

export interface Tokens {
  readonly acceso: string;
  readonly refresco: string;
  readonly tipo: string;
  readonly expiraEnSegundos: number;
}

export interface Sesion {
  readonly tokens: Tokens;
  readonly usuario: Usuario;
  readonly debeCambiarContrasena: boolean;
}

/** Vias de acceso habilitadas en la instalacion. */
export interface MetodosAcceso {
  readonly local: boolean;
  readonly google: boolean;
  readonly ldap: boolean;
  readonly urlGoogle: string | null;
}

export interface PermisoCatalogo {
  readonly codigo: Permiso;
  readonly modulo: string;
  readonly accion: string;
}

// ---------------------------------------------------------------------------
// Personas
// ---------------------------------------------------------------------------

export interface Persona {
  readonly id: string;
  readonly cedula: string;
  readonly nombres: string;
  readonly apellidos: string;
  readonly nombreCompleto: string;
  readonly emailInstitucional: string | null;
  readonly emailPersonal: string | null;
  readonly telefono: string | null;
  readonly tipoVinculacion: TipoVinculacion;
  readonly unidad: string | null;
  readonly cargo: string | null;
  readonly codigoEmpleado: string | null;
  readonly fechaIngreso: string | null;
  readonly activo: boolean;
  readonly observaciones: string | null;
  readonly titulosRegistrados: number;
  readonly totalConsultas: number;
  readonly ultimaConsultaEn: string | null;
  readonly ultimaConsultaEstado: EstadoConsulta | null;
  readonly ultimaConsultaExitosaEn: string | null;
  readonly creadoEn: string;
  readonly actualizadoEn: string;
}

export interface PersonaDetalle {
  readonly persona: Persona;
  readonly titulos: readonly Titulo[];
  readonly totalTitulos: number;
  readonly titulosVigentes: number;
}

export interface FiltroPersonas {
  readonly texto?: string;
  readonly unidad?: string;
  readonly tipoVinculacion?: TipoVinculacion;
  readonly activo?: boolean;
  /** `false` aisla a las personas sin ningun titulo registrado. */
  readonly conTitulos?: boolean;
  readonly nuncaConsultadas?: boolean;
  readonly estadoUltimaConsulta?: EstadoConsulta;
}

export interface DatosPersona {
  readonly cedula: string;
  readonly nombres: string;
  readonly apellidos: string;
  readonly emailInstitucional?: string | null;
  readonly emailPersonal?: string | null;
  readonly telefono?: string | null;
  readonly tipoVinculacion?: TipoVinculacion;
  readonly unidad?: string | null;
  readonly cargo?: string | null;
  readonly codigoEmpleado?: string | null;
  readonly fechaIngreso?: string | null;
  readonly fechaNacimiento?: string | null;
  readonly observaciones?: string | null;
}

export type CambiosPersona = Partial<Omit<DatosPersona, 'cedula'>> & {
  readonly activo?: boolean;
};

export interface FilaImportacion {
  readonly cedula: string;
  readonly nombres: string;
  readonly apellidos: string;
  readonly emailInstitucional?: string | null;
  readonly tipoVinculacion?: string | null;
  readonly unidad?: string | null;
  readonly cargo?: string | null;
  readonly codigoEmpleado?: string | null;
}

export interface ErrorImportacion {
  readonly fila: number;
  readonly cedula: string;
  readonly motivo: string;
}

export interface ResultadoImportacion {
  readonly totalFilas: number;
  readonly creadas: number;
  readonly duplicadas: number;
  readonly rechazadas: readonly ErrorImportacion[];
  readonly exitosa: boolean;
}

// ---------------------------------------------------------------------------
// Titulos
// ---------------------------------------------------------------------------

export interface Titulo {
  readonly id: string;
  readonly personaId: string;
  readonly denominacion: string;
  readonly institucion: string;
  readonly nivel: NivelTitulo;
  readonly numeroRegistro: string | null;
  readonly fechaRegistro: string | null;
  readonly fechaGraduacion: string | null;
  readonly areaConocimiento: string | null;
  readonly pais: string;
  readonly observacionRegistro: string | null;
  readonly origen: OrigenTitulo;
  readonly estado: EstadoTitulo;
  readonly esPosgrado: boolean;
  /** Casos que un analista deberia revisar a mano. */
  readonly requiereAtencion: boolean;
  readonly verificado: boolean;
  readonly verificadoEn: string | null;
  readonly vistoPrimeraVezEn: string;
  readonly vistoUltimaVezEn: string;
  readonly retiradoEn: string | null;
}

export interface FiltroTitulos {
  readonly texto?: string;
  readonly personaId?: string;
  readonly nivel?: NivelTitulo;
  readonly estado?: EstadoTitulo;
  readonly institucion?: string;
  readonly verificado?: boolean;
  readonly requiereAtencion?: boolean;
  readonly registroDesde?: string;
  readonly registroHasta?: string;
}

export interface DatosTitulo {
  readonly personaId: string;
  readonly denominacion: string;
  readonly institucion: string;
  readonly nivel?: NivelTitulo | null;
  readonly numeroRegistro?: string | null;
  readonly fechaRegistro?: string | null;
  readonly fechaGraduacion?: string | null;
  readonly areaConocimiento?: string | null;
  readonly pais?: string;
  readonly observacionRegistro?: string | null;
}

export type CambiosTitulo = Partial<Omit<DatosTitulo, 'personaId'>>;

// ---------------------------------------------------------------------------
// Consultas
// ---------------------------------------------------------------------------

export interface Cambio {
  readonly tipo: string;
  readonly tituloId: string | null;
  readonly denominacion: string;
  readonly detalle: Record<string, unknown>;
}

export interface ConsultaLog {
  readonly id: string;
  readonly personaId: string;
  readonly cedula: string;
  readonly estado: EstadoConsulta;
  readonly jobId: string | null;
  readonly proveedor: string;
  readonly intento: number;
  readonly iniciadoEn: string;
  readonly finalizadoEn: string | null;
  readonly duracionMs: number | null;
  readonly titulosEncontrados: number;
  readonly titulosNuevos: number;
  readonly titulosActualizados: number;
  readonly titulosRetirados: number;
  readonly huboCambios: boolean;
  readonly resumen: string;
  readonly mensaje: string | null;
  readonly tipoError: string | null;
  readonly codigoHttp: number | null;
  readonly cambios: readonly Cambio[];
  /** Solo viene informado cuando el estado es `DESAFIO_PENDIENTE`. */
  readonly desafioId: string | null;
}

export interface FiltroLogs {
  readonly personaId?: string;
  readonly jobId?: string;
  readonly cedula?: string;
  readonly estado?: EstadoConsulta;
  readonly soloErrores?: boolean;
  readonly soloConCambios?: boolean;
  readonly desde?: string;
  readonly hasta?: string;
}

export interface ResultadoConsulta {
  readonly log: ConsultaLog;
  /** `true` cuando el proveedor exige verificacion humana. */
  readonly requiereIntervencion: boolean;
  readonly desafioId: string | null;
  readonly resumenCambios: Record<string, number>;
}

export interface JobCobertura {
  readonly id: string;
  readonly nombre: string;
  readonly estado: EstadoJob;
  readonly periodoInicio: string;
  readonly periodoFin: string;
  readonly totalItems: number;
  readonly completados: number;
  readonly fallidos: number;
  readonly omitidos: number;
  readonly esperandoDesafio: number;
  readonly pendientes: number;
  readonly porcentajeAvance: number;
  readonly estaCubierto: boolean;
  readonly fallosConsecutivos: number;
  /** `true` si lo detuvo el cortacircuitos, no un operador. */
  readonly pausadoAutomaticamente: boolean;
  readonly motivoPausa: string | null;
  readonly ritmoRequeridoPorHora: number;
  readonly iniciadoEn: string | null;
  readonly finalizadoEn: string | null;
  readonly ultimaActividadEn: string | null;
  readonly configuracion: Record<string, unknown>;
}

export interface DatosJob {
  readonly nombre: string;
  readonly periodoDias?: number | null;
  readonly limitePersonas?: number | null;
  readonly iniciarInmediatamente?: boolean;
  readonly distribuirEnPeriodo?: boolean;
}

export interface JobCreado {
  readonly job: JobCobertura;
  readonly factible: boolean;
  readonly consultasDiariasEstimadas: number;
  readonly diasNecesarios: number;
  readonly advertencia: string | null;
}

export type AccionJob = 'iniciar' | 'pausar' | 'reanudar' | 'cancelar';

export interface PasoJob {
  readonly jobId: string;
  readonly huboConsulta: boolean;
  readonly esperarSegundos: number;
  readonly motivo: string;
  readonly jobCompletado: boolean;
  readonly jobPausado: boolean;
  readonly resultado: ResultadoConsulta | null;
}

/** Configuracion y estado vigentes de la politica de ritmo. */
export interface EstadoPlanificador {
  readonly habilitado: boolean;
  readonly proveedor: string;
  readonly requiereVerificacionHumana: boolean;
  readonly horaLocal: string;
  readonly franjaActual: 'PICO' | 'VALLE' | 'INACTIVA';
  readonly pesoFranja: number;
  readonly enHorarioOperativo: boolean;
  readonly proximaApertura: string | null;
  readonly capacidadDiariaEstimada: number;
  readonly configuracion: {
    readonly periodoDias: number;
    readonly maxConsultasPorHora: number;
    readonly franjaPico: string;
    readonly franjaValle: string;
    readonly demoraSegundos: readonly number[];
    readonly umbralCortacircuitos: number;
  };
}

// ---------------------------------------------------------------------------
// Tablero
// ---------------------------------------------------------------------------

export interface Conteo {
  readonly etiqueta: string;
  readonly valor: number;
  readonly porcentaje: number;
}

export interface PuntoSerie {
  readonly fecha: string;
  readonly valor: number;
}

export interface ResumenCobertura {
  readonly totalPersonas: number;
  readonly personasActivas: number;
  readonly conTitulos: number;
  readonly sinTitulos: number;
  readonly nuncaConsultadas: number;
  readonly consultadasEnPeriodo: number;
  readonly conErrorUltimaConsulta: number;
  readonly porcentajeCobertura: number;
  readonly porcentajeConTitulos: number;
}

export interface ResumenTitulos {
  readonly total: number;
  readonly vigentes: number;
  readonly retirados: number;
  readonly porVerificar: number;
  readonly verificados: number;
  readonly posgrados: number;
  readonly porNivel: readonly Conteo[];
  readonly porInstitucion: readonly Conteo[];
}

export interface ResumenConsultas {
  readonly totalPeriodo: number;
  readonly exitosas: number;
  readonly sinDatos: number;
  readonly conError: number;
  readonly esperandoDesafio: number;
  readonly conCambios: number;
  readonly duracionPromedioMs: number;
  readonly tasaExito: number;
  readonly porEstado: readonly Conteo[];
  readonly tendenciaDiaria: readonly PuntoSerie[];
}

export interface Tablero {
  readonly cobertura: ResumenCobertura;
  readonly titulos: ResumenTitulos;
  readonly consultas: ResumenConsultas;
  readonly personasPorUnidad: readonly Conteo[];
  readonly personasPorVinculacion: readonly Conteo[];
  readonly generadoEn: string;
}

// ---------------------------------------------------------------------------
// Administracion
// ---------------------------------------------------------------------------

export interface DatosUsuario {
  readonly email: string;
  readonly nombreCompleto: string;
  readonly contrasena?: string | null;
  readonly roles: readonly string[];
  readonly activo?: boolean;
  readonly debeCambiarContrasena?: boolean;
  readonly facultadesIds?: readonly string[];
  readonly carrerasIds?: readonly string[];
}

export interface CambiosUsuario {
  readonly nombreCompleto?: string;
  readonly email?: string;
  readonly activo?: boolean;
  readonly roles?: readonly string[];
  /** Omitido deja el alcance como estaba; vacio lo borra. */
  readonly facultadesIds?: readonly string[];
  readonly carrerasIds?: readonly string[];
}
