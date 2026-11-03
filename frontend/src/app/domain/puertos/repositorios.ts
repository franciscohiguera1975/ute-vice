/**
 * Puertos del frontend.
 *
 * Se declaran como clases abstractas porque en Angular una clase abstracta
 * sirve a la vez de contrato y de token de inyeccion, sin necesidad de crear un
 * `InjectionToken` aparte.
 *
 * Los componentes dependen de estas abstracciones, nunca de `HttpClient`. La
 * consecuencia practica: una prueba de componente inyecta una implementacion en
 * memoria y no necesita simular peticiones HTTP; y si manana la API cambia de
 * REST a otra cosa, solo cambia la capa `data`.
 */

import type { Observable } from 'rxjs';

import type {
  AccionJob,
  ArchivoDescarga,
  CambiosPersona,
  CambiosTitulo,
  CambiosUsuario,
  ConsultaLog,
  DatosJob,
  DatosPersona,
  DatosTitulo,
  DatosUsuario,
  EstadoPlanificador,
  FilaImportacion,
  FiltroLogs,
  FiltroPersonas,
  FiltroTitulos,
  FormatoReporte,
  JobCobertura,
  JobCreado,
  MetodosAcceso,
  Pagina,
  ParametrosPaginacion,
  PasoJob,
  PermisoCatalogo,
  Persona,
  PersonaDetalle,
  ResultadoConsulta,
  ResultadoImportacion,
  Rol,
  Sesion,
  Tablero,
  Titulo,
  Usuario,
} from '../modelos';

// ---------------------------------------------------------------------------
export abstract class RepositorioAutenticacion {
  abstract metodosDisponibles(): Observable<MetodosAcceso>;
  abstract iniciarSesion(email: string, contrasena: string): Observable<Sesion>;
  abstract iniciarSesionLdap(usuario: string, contrasena: string): Observable<Sesion>;
  abstract completarAccesoGoogle(codigo: string): Observable<Sesion>;
  abstract refrescar(tokenRefresco: string): Observable<Sesion>;
  abstract cerrarSesion(tokenRefresco: string): Observable<void>;
  abstract perfil(): Observable<Usuario>;
  abstract cambiarContrasena(actual: string, nueva: string): Observable<void>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioPersonas {
  abstract listar(
    filtro: FiltroPersonas,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<Persona>>;
  abstract obtener(id: string): Observable<PersonaDetalle>;
  abstract obtenerPorCedula(cedula: string): Observable<PersonaDetalle>;
  abstract crear(datos: DatosPersona): Observable<Persona>;
  abstract actualizar(id: string, cambios: CambiosPersona): Observable<Persona>;
  abstract eliminar(id: string): Observable<void>;
  abstract importar(filas: readonly FilaImportacion[]): Observable<ResultadoImportacion>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioTitulos {
  abstract listar(
    filtro: FiltroTitulos,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<Titulo>>;
  abstract obtener(id: string): Observable<Titulo>;
  abstract crear(datos: DatosTitulo): Observable<Titulo>;
  abstract actualizar(id: string, cambios: CambiosTitulo): Observable<Titulo>;
  abstract verificar(id: string): Observable<Titulo>;
  abstract eliminar(id: string): Observable<void>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioConsultas {
  abstract consultarPersona(personaId: string, forzar?: boolean): Observable<ResultadoConsulta>;
  abstract listarLogs(
    filtro: FiltroLogs,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<ConsultaLog>>;

  abstract listarJobs(paginacion: ParametrosPaginacion): Observable<Pagina<JobCobertura>>;
  abstract obtenerJob(id: string): Observable<JobCobertura>;
  abstract crearJob(datos: DatosJob): Observable<JobCreado>;
  abstract controlarJob(id: string, accion: AccionJob, motivo?: string): Observable<JobCobertura>;
  abstract avanzarJob(id: string): Observable<PasoJob>;

  /**
   * Aporta la respuesta humana a un desafio de verificacion.
   *
   * El sistema no resuelve el desafio por su cuenta: lo muestra a un operador,
   * que lo lee y transcribe la respuesta. Es una decision de diseno explicita
   * documentada en `docs/SENESCYT.md`.
   */
  abstract resolverDesafio(desafioId: string, respuesta: string): Observable<ResultadoConsulta>;

  abstract estadoPlanificador(): Observable<EstadoPlanificador>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioTablero {
  abstract obtener(dias: number): Observable<Tablero>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioReportes {
  abstract formatosDisponibles(): Observable<readonly FormatoReporte[]>;
  abstract personas(
    formato: FormatoReporte,
    filtro: FiltroPersonas,
    incluirTitulos: boolean,
  ): Observable<ArchivoDescarga>;
  abstract titulos(formato: FormatoReporte, filtro: FiltroTitulos): Observable<ArchivoDescarga>;
  abstract consultas(formato: FormatoReporte, filtro: FiltroLogs): Observable<ArchivoDescarga>;
}

// ---------------------------------------------------------------------------
export abstract class RepositorioAdministracion {
  abstract listarUsuarios(
    paginacion: ParametrosPaginacion,
    texto?: string,
    activo?: boolean,
    rol?: string,
  ): Observable<Pagina<Usuario>>;
  abstract obtenerUsuario(id: string): Observable<Usuario>;
  abstract crearUsuario(datos: DatosUsuario): Observable<Usuario>;
  abstract actualizarUsuario(id: string, cambios: CambiosUsuario): Observable<Usuario>;
  abstract restablecerContrasena(
    id: string,
    contrasena: string,
    forzarCambio: boolean,
  ): Observable<void>;
  abstract eliminarUsuario(id: string): Observable<void>;

  abstract listarRoles(): Observable<readonly Rol[]>;
  abstract actualizarRol(
    codigo: string,
    cambios: { nombre?: string; descripcion?: string; permisos?: readonly string[] },
  ): Observable<Rol>;
  abstract listarPermisos(): Observable<readonly PermisoCatalogo[]>;
}
