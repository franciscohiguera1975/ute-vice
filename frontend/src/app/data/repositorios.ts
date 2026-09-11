/**
 * Implementaciones HTTP de los puertos del dominio.
 *
 * Cada clase se limita a traducir una llamada del dominio en una ruta de la
 * API. Toda la logica —validaciones, reglas, decisiones— vive en el backend o
 * en los componentes; aqui no hay ninguna, y eso es intencional: una capa de
 * datos con logica es una capa de datos que hay que probar dos veces.
 */

import { Injectable, inject } from '@angular/core';
import { type Observable, map } from 'rxjs';

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
} from '@domain/modelos';
import {
  RepositorioAdministracion,
  RepositorioAutenticacion,
  RepositorioConsultas,
  RepositorioPersonas,
  RepositorioReportes,
  RepositorioTablero,
  RepositorioTitulos,
} from '@domain/puertos';

import { ApiService } from './api.service';

// ---------------------------------------------------------------------------
@Injectable()
export class AutenticacionHttp extends RepositorioAutenticacion {
  private readonly api = inject(ApiService);

  metodosDisponibles(): Observable<MetodosAcceso> {
    return this.api.get<MetodosAcceso>('/auth/metodos');
  }

  iniciarSesion(email: string, contrasena: string): Observable<Sesion> {
    return this.api.post<Sesion>('/auth/login', { email, contrasena });
  }

  iniciarSesionLdap(usuario: string, contrasena: string): Observable<Sesion> {
    return this.api.post<Sesion>('/auth/login/ldap', { usuario, contrasena });
  }

  completarAccesoGoogle(codigo: string): Observable<Sesion> {
    return this.api.get<Sesion>('/auth/google/callback', { code: codigo });
  }

  refrescar(tokenRefresco: string): Observable<Sesion> {
    return this.api.post<Sesion>('/auth/refrescar', { tokenRefresco });
  }

  cerrarSesion(tokenRefresco: string): Observable<void> {
    return this.api.post<void>('/auth/logout', { tokenRefresco });
  }

  perfil(): Observable<Usuario> {
    return this.api
      .get<{ usuario: Usuario }>('/auth/perfil')
      .pipe(map((respuesta) => respuesta.usuario));
  }

  cambiarContrasena(actual: string, nueva: string): Observable<void> {
    return this.api.post<void>('/auth/cambiar-contrasena', {
      contrasenaActual: actual,
      contrasenaNueva: nueva,
    });
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class PersonasHttp extends RepositorioPersonas {
  private readonly api = inject(ApiService);

  listar(filtro: FiltroPersonas, paginacion: ParametrosPaginacion): Observable<Pagina<Persona>> {
    return this.api.listar<Persona>('/personas', filtro, paginacion);
  }

  obtener(id: string): Observable<PersonaDetalle> {
    return this.api.get<PersonaDetalle>(`/personas/${id}`);
  }

  obtenerPorCedula(cedula: string): Observable<PersonaDetalle> {
    return this.api.get<PersonaDetalle>(`/personas/cedula/${cedula}`);
  }

  crear(datos: DatosPersona): Observable<Persona> {
    return this.api.post<Persona>('/personas', datos);
  }

  actualizar(id: string, cambios: CambiosPersona): Observable<Persona> {
    return this.api.patch<Persona>(`/personas/${id}`, cambios);
  }

  eliminar(id: string): Observable<void> {
    return this.api.delete<void>(`/personas/${id}`);
  }

  importar(filas: readonly FilaImportacion[]): Observable<ResultadoImportacion> {
    return this.api.post<ResultadoImportacion>('/personas/importar', filas);
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class TitulosHttp extends RepositorioTitulos {
  private readonly api = inject(ApiService);

  listar(filtro: FiltroTitulos, paginacion: ParametrosPaginacion): Observable<Pagina<Titulo>> {
    return this.api.listar<Titulo>('/titulos', filtro, paginacion);
  }

  obtener(id: string): Observable<Titulo> {
    return this.api.get<Titulo>(`/titulos/${id}`);
  }

  crear(datos: DatosTitulo): Observable<Titulo> {
    return this.api.post<Titulo>('/titulos', datos);
  }

  actualizar(id: string, cambios: CambiosTitulo): Observable<Titulo> {
    return this.api.patch<Titulo>(`/titulos/${id}`, cambios);
  }

  verificar(id: string): Observable<Titulo> {
    return this.api.post<Titulo>(`/titulos/${id}/verificar`);
  }

  eliminar(id: string): Observable<void> {
    return this.api.delete<void>(`/titulos/${id}`);
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class ConsultasHttp extends RepositorioConsultas {
  private readonly api = inject(ApiService);

  consultarPersona(personaId: string, forzar = false): Observable<ResultadoConsulta> {
    return this.api.post<ResultadoConsulta>(
      `/consultas/personas/${personaId}`,
      undefined,
      forzar ? { forzar: true } : undefined,
    );
  }

  listarLogs(filtro: FiltroLogs, paginacion: ParametrosPaginacion): Observable<Pagina<ConsultaLog>> {
    return this.api.listar<ConsultaLog>('/consultas/logs', filtro, paginacion);
  }

  listarJobs(paginacion: ParametrosPaginacion): Observable<Pagina<JobCobertura>> {
    return this.api.listar<JobCobertura>('/consultas/jobs', {}, paginacion);
  }

  obtenerJob(id: string): Observable<JobCobertura> {
    return this.api.get<JobCobertura>(`/consultas/jobs/${id}`);
  }

  crearJob(datos: DatosJob): Observable<JobCreado> {
    return this.api.post<JobCreado>('/consultas/jobs', datos);
  }

  controlarJob(id: string, accion: AccionJob, motivo?: string): Observable<JobCobertura> {
    return this.api.post<JobCobertura>(`/consultas/jobs/${id}/control`, { accion, motivo });
  }

  avanzarJob(id: string): Observable<PasoJob> {
    return this.api.post<PasoJob>(`/consultas/jobs/${id}/avanzar`);
  }

  resolverDesafio(desafioId: string, respuesta: string): Observable<ResultadoConsulta> {
    return this.api.post<ResultadoConsulta>('/consultas/desafios/resolver', {
      desafioId,
      respuesta,
    });
  }

  estadoPlanificador(): Observable<EstadoPlanificador> {
    return this.api.get<EstadoPlanificador>('/consultas/estado-planificador');
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class TableroHttp extends RepositorioTablero {
  private readonly api = inject(ApiService);

  obtener(dias: number): Observable<Tablero> {
    return this.api.get<Tablero>('/tablero', { dias });
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class ReportesHttp extends RepositorioReportes {
  private readonly api = inject(ApiService);

  formatosDisponibles(): Observable<readonly FormatoReporte[]> {
    return this.api.get<FormatoReporte[]>('/reportes/formatos');
  }

  personas(
    formato: FormatoReporte,
    filtro: FiltroPersonas,
    incluirTitulos: boolean,
  ): Observable<ArchivoDescarga> {
    return this.api.descargar(
      '/reportes/personas',
      { formato, ...filtro, incluirTitulos },
      `personas.${formato.toLowerCase()}`,
    );
  }

  titulos(formato: FormatoReporte, filtro: FiltroTitulos): Observable<ArchivoDescarga> {
    return this.api.descargar(
      '/reportes/titulos',
      { formato, ...filtro },
      `titulos.${formato.toLowerCase()}`,
    );
  }

  consultas(formato: FormatoReporte, filtro: FiltroLogs): Observable<ArchivoDescarga> {
    return this.api.descargar(
      '/reportes/consultas',
      { formato, ...filtro },
      `consultas.${formato.toLowerCase()}`,
    );
  }
}

// ---------------------------------------------------------------------------
@Injectable()
export class AdministracionHttp extends RepositorioAdministracion {
  private readonly api = inject(ApiService);

  listarUsuarios(
    paginacion: ParametrosPaginacion,
    texto?: string,
    activo?: boolean,
    rol?: string,
  ): Observable<Pagina<Usuario>> {
    return this.api.listar<Usuario>('/usuarios', { texto, activo, rol }, paginacion);
  }

  obtenerUsuario(id: string): Observable<Usuario> {
    return this.api.get<Usuario>(`/usuarios/${id}`);
  }

  crearUsuario(datos: DatosUsuario): Observable<Usuario> {
    return this.api.post<Usuario>('/usuarios', datos);
  }

  actualizarUsuario(id: string, cambios: CambiosUsuario): Observable<Usuario> {
    return this.api.patch<Usuario>(`/usuarios/${id}`, cambios);
  }

  restablecerContrasena(
    id: string,
    contrasena: string,
    forzarCambio: boolean,
  ): Observable<void> {
    return this.api.post<void>(`/usuarios/${id}/contrasena`, {
      contrasenaNueva: contrasena,
      forzarCambio,
    });
  }

  eliminarUsuario(id: string): Observable<void> {
    return this.api.delete<void>(`/usuarios/${id}`);
  }

  listarRoles(): Observable<readonly Rol[]> {
    return this.api.get<Rol[]>('/roles');
  }

  actualizarRol(
    codigo: string,
    cambios: { nombre?: string; descripcion?: string; permisos?: readonly string[] },
  ): Observable<Rol> {
    return this.api.patch<Rol>(`/roles/${codigo}`, cambios);
  }

  listarPermisos(): Observable<readonly PermisoCatalogo[]> {
    return this.api.get<PermisoCatalogo[]>('/permisos');
  }
}

// ---------------------------------------------------------------------------
/**
 * Enlaza cada puerto con su implementacion HTTP.
 *
 * Es el equivalente al contenedor de dependencias del backend: el unico sitio
 * del frontend donde se decide que clase concreta cumple cada contrato.
 */
export const PROVEEDORES_DATOS = [
  { provide: RepositorioAutenticacion, useClass: AutenticacionHttp },
  { provide: RepositorioPersonas, useClass: PersonasHttp },
  { provide: RepositorioTitulos, useClass: TitulosHttp },
  { provide: RepositorioConsultas, useClass: ConsultasHttp },
  { provide: RepositorioTablero, useClass: TableroHttp },
  { provide: RepositorioReportes, useClass: ReportesHttp },
  { provide: RepositorioAdministracion, useClass: AdministracionHttp },
];
