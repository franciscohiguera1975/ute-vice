/**
 * Enumeraciones del dominio. Reflejan exactamente las del backend.
 *
 * Se declaran como objetos constantes con tipos derivados en lugar de `enum` de
 * TypeScript: los valores viajan tal cual en el JSON, y asi no hay que traducir
 * en los bordes ni existe riesgo de que el numero de un `enum` numerico se
 * desalinee del backend.
 */

export const AuthProvider = {
  LOCAL: 'LOCAL',
  GOOGLE: 'GOOGLE',
  LDAP: 'LDAP',
} as const;
export type AuthProvider = (typeof AuthProvider)[keyof typeof AuthProvider];

export const RolCodigo = {
  ADMIN: 'ADMIN',
  COORDINADOR: 'COORDINADOR',
  ANALISTA: 'ANALISTA',
  CONSULTA: 'CONSULTA',
} as const;
export type RolCodigo = (typeof RolCodigo)[keyof typeof RolCodigo];

/**
 * Permisos atomicos.
 *
 * La interfaz decide que mostrar preguntando por permisos, nunca por roles —la
 * misma regla que aplica el backend—. Si se agrega un rol nuevo, ninguna
 * plantilla cambia.
 */
export const Permiso = {
  PERSONAS_LEER: 'personas:leer',
  PERSONAS_ESCRIBIR: 'personas:escribir',
  PERSONAS_ELIMINAR: 'personas:eliminar',
  PERSONAS_IMPORTAR: 'personas:importar',

  TITULOS_LEER: 'titulos:leer',
  TITULOS_ESCRIBIR: 'titulos:escribir',
  TITULOS_ELIMINAR: 'titulos:eliminar',
  TITULOS_VERIFICAR: 'titulos:verificar',

  CONSULTAS_LEER: 'consultas:leer',
  CONSULTAS_EJECUTAR: 'consultas:ejecutar',
  CONSULTAS_RESOLVER: 'consultas:resolver',
  CONSULTAS_ADMINISTRAR: 'consultas:administrar',

  DISTRIBUTIVO_LEER: 'distributivo:leer',
  DISTRIBUTIVO_ESCRIBIR: 'distributivo:escribir',
  DISTRIBUTIVO_ELIMINAR: 'distributivo:eliminar',
  DISTRIBUTIVO_IMPORTAR: 'distributivo:importar',

  CATALOGOS_LEER: 'catalogos:leer',
  CATALOGOS_ESCRIBIR: 'catalogos:escribir',

  REPORTES_GENERAR: 'reportes:generar',
  DASHBOARD_VER: 'dashboard:ver',

  USUARIOS_LEER: 'usuarios:leer',
  USUARIOS_ESCRIBIR: 'usuarios:escribir',
  USUARIOS_ELIMINAR: 'usuarios:eliminar',
  ROLES_ADMINISTRAR: 'roles:administrar',
  AUDITORIA_LEER: 'auditoria:leer',
} as const;
export type Permiso = (typeof Permiso)[keyof typeof Permiso];

export const TipoVinculacion = {
  DOCENTE: 'DOCENTE',
  ADMINISTRATIVO: 'ADMINISTRATIVO',
  DIRECTIVO: 'DIRECTIVO',
  SERVICIOS: 'SERVICIOS',
  OTRO: 'OTRO',
} as const;
export type TipoVinculacion = (typeof TipoVinculacion)[keyof typeof TipoVinculacion];

export const NivelTitulo = {
  TECNICO: 'TECNICO',
  TECNOLOGICO: 'TECNOLOGICO',
  TERCER_NIVEL: 'TERCER_NIVEL',
  ESPECIALIZACION: 'ESPECIALIZACION',
  MAESTRIA: 'MAESTRIA',
  DOCTORADO: 'DOCTORADO',
  NO_DETERMINADO: 'NO_DETERMINADO',
} as const;
export type NivelTitulo = (typeof NivelTitulo)[keyof typeof NivelTitulo];

export const OrigenTitulo = {
  SENESCYT: 'SENESCYT',
  MANUAL: 'MANUAL',
  IMPORTACION: 'IMPORTACION',
} as const;
export type OrigenTitulo = (typeof OrigenTitulo)[keyof typeof OrigenTitulo];

export const EstadoTitulo = {
  VIGENTE: 'VIGENTE',
  RETIRADO: 'RETIRADO',
  POR_VERIFICAR: 'POR_VERIFICAR',
} as const;
export type EstadoTitulo = (typeof EstadoTitulo)[keyof typeof EstadoTitulo];

export const EstadoConsulta = {
  EXITO: 'EXITO',
  SIN_DATOS: 'SIN_DATOS',
  DESAFIO_PENDIENTE: 'DESAFIO_PENDIENTE',
  ERROR_PROVEEDOR: 'ERROR_PROVEEDOR',
  ERROR_RED: 'ERROR_RED',
  ERROR_DATOS: 'ERROR_DATOS',
  RECHAZADO: 'RECHAZADO',
  CANCELADO: 'CANCELADO',
} as const;
export type EstadoConsulta = (typeof EstadoConsulta)[keyof typeof EstadoConsulta];

export const ESTADOS_CONSULTA_ERROR: readonly EstadoConsulta[] = [
  EstadoConsulta.ERROR_PROVEEDOR,
  EstadoConsulta.ERROR_RED,
  EstadoConsulta.ERROR_DATOS,
  EstadoConsulta.RECHAZADO,
];

export const esErrorDeConsulta = (estado: EstadoConsulta): boolean =>
  ESTADOS_CONSULTA_ERROR.includes(estado);

export const EstadoJob = {
  BORRADOR: 'BORRADOR',
  PROGRAMADO: 'PROGRAMADO',
  EN_CURSO: 'EN_CURSO',
  PAUSADO: 'PAUSADO',
  COMPLETADO: 'COMPLETADO',
  CANCELADO: 'CANCELADO',
} as const;
export type EstadoJob = (typeof EstadoJob)[keyof typeof EstadoJob];

export const FormatoReporte = {
  XLSX: 'XLSX',
  CSV: 'CSV',
  PDF: 'PDF',
} as const;
export type FormatoReporte = (typeof FormatoReporte)[keyof typeof FormatoReporte];

// ---------------------------------------------------------------------------
// Etiquetas para la interfaz
// ---------------------------------------------------------------------------

/**
 * Textos legibles de cada valor.
 *
 * Se centralizan aqui para que un mismo estado se lea igual en la tabla, en el
 * detalle y en el tablero. Repartir las etiquetas por las plantillas garantiza
 * que tarde o temprano diverjan.
 */
export const ETIQUETAS_NIVEL: Record<NivelTitulo, string> = {
  TECNICO: 'Tecnico',
  TECNOLOGICO: 'Tecnologico',
  TERCER_NIVEL: 'Tercer nivel',
  ESPECIALIZACION: 'Especializacion',
  MAESTRIA: 'Maestria',
  DOCTORADO: 'Doctorado',
  NO_DETERMINADO: 'Sin determinar',
};

export const ETIQUETAS_ESTADO_TITULO: Record<EstadoTitulo, string> = {
  VIGENTE: 'Vigente',
  RETIRADO: 'Retirado',
  POR_VERIFICAR: 'Por verificar',
};

export const ETIQUETAS_ESTADO_CONSULTA: Record<EstadoConsulta, string> = {
  EXITO: 'Exito',
  SIN_DATOS: 'Sin titulos',
  DESAFIO_PENDIENTE: 'Espera verificacion',
  ERROR_PROVEEDOR: 'Error del proveedor',
  ERROR_RED: 'Error de red',
  ERROR_DATOS: 'Dato invalido',
  RECHAZADO: 'Rechazado',
  CANCELADO: 'Cancelado',
};

export const ETIQUETAS_ESTADO_JOB: Record<EstadoJob, string> = {
  BORRADOR: 'Borrador',
  PROGRAMADO: 'Programado',
  EN_CURSO: 'En curso',
  PAUSADO: 'Pausado',
  COMPLETADO: 'Completado',
  CANCELADO: 'Cancelado',
};

export const ETIQUETAS_VINCULACION: Record<TipoVinculacion, string> = {
  DOCENTE: 'Docente',
  ADMINISTRATIVO: 'Administrativo',
  DIRECTIVO: 'Directivo',
  SERVICIOS: 'Servicios',
  OTRO: 'Otro',
};

export const ETIQUETAS_ORIGEN: Record<OrigenTitulo, string> = {
  SENESCYT: 'Registro nacional',
  MANUAL: 'Carga manual',
  IMPORTACION: 'Importacion',
};

/** Tono visual asociado a cada estado. Lo consumen las insignias. */
export type Tono = 'exito' | 'aviso' | 'error' | 'neutro' | 'info';

export const TONO_ESTADO_CONSULTA: Record<EstadoConsulta, Tono> = {
  EXITO: 'exito',
  SIN_DATOS: 'neutro',
  DESAFIO_PENDIENTE: 'aviso',
  ERROR_PROVEEDOR: 'error',
  ERROR_RED: 'error',
  ERROR_DATOS: 'aviso',
  RECHAZADO: 'error',
  CANCELADO: 'neutro',
};

export const TONO_ESTADO_TITULO: Record<EstadoTitulo, Tono> = {
  VIGENTE: 'exito',
  RETIRADO: 'error',
  POR_VERIFICAR: 'aviso',
};

export const TONO_ESTADO_JOB: Record<EstadoJob, Tono> = {
  BORRADOR: 'neutro',
  PROGRAMADO: 'info',
  EN_CURSO: 'exito',
  PAUSADO: 'aviso',
  COMPLETADO: 'info',
  CANCELADO: 'neutro',
};
