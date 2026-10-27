import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import type { ErrorApi, ResultadoCargaEstudiantes } from '@domain/modelos';
import { RepositorioEstudiantes } from '@domain/puertos';

/** Extensiones que acepta el lector del backend. */
const EXTENSIONES = ['.xlsx', '.xlsm'];

/** Mismo tope que el endpoint. Comprobarlo aqui evita una subida inutil. */
const TOPE_MB = 25;

/**
 * Carga de un reporte de matricula estudiantil de Banner.
 *
 * A diferencia de la carga del PAO, no se pide ningun dato aparte: el reporte
 * trae el periodo como una columna mas de cada fila, asi que basta con el
 * archivo.
 */
@Component({
  selector: 'ute-importar-estudiantes',
  standalone: true,
  imports: [DecimalPipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './importar-estudiantes.component.html',
  styleUrl: './importar-estudiantes.component.scss',
})
export class ImportarEstudiantesComponent {
  private readonly repositorio = inject(RepositorioEstudiantes);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly EXTENSIONES = EXTENSIONES;
  protected readonly TOPE_MB = TOPE_MB;

  protected readonly archivo = signal<File | null>(null);
  protected readonly subiendo = signal(false);
  protected readonly resultado = signal<ResultadoCargaEstudiantes | null>(null);
  protected readonly errorArchivo = signal('');

  /** Solo se muestran las primeras; el resto se resume en una linea. */
  protected readonly TOPE_LISTA = 15;

  protected readonly puedeSubir = computed(() => this.archivo() !== null && !this.subiendo());

  protected readonly matriculasTocadas = computed(() => {
    const r = this.resultado();
    return r ? r.matriculasCreadas + r.matriculasActualizadas : 0;
  });

  // ------------------------------------------------------------- acciones
  protected elegir(evento: Event): void {
    const entrada = evento.target as HTMLInputElement;
    const elegido = entrada.files?.[0] ?? null;
    this.resultado.set(null);
    this.errorArchivo.set('');

    if (!elegido) {
      this.archivo.set(null);
      return;
    }

    const nombre = elegido.name.toLowerCase();
    if (!EXTENSIONES.some((e) => nombre.endsWith(e))) {
      this.errorArchivo.set(`Se espera un archivo ${EXTENSIONES.join(', ')}`);
      this.archivo.set(null);
      return;
    }
    if (elegido.size > TOPE_MB * 1024 * 1024) {
      this.errorArchivo.set(`El archivo supera el tope de ${TOPE_MB} MB`);
      this.archivo.set(null);
      return;
    }

    this.archivo.set(elegido);
  }

  protected subir(): void {
    const elegido = this.archivo();
    if (!elegido) return;

    this.subiendo.set(true);
    this.resultado.set(null);

    this.repositorio.cargar({ archivo: elegido }).subscribe({
      next: (resultado) => {
        this.resultado.set(resultado);
        this.subiendo.set(false);
        this.notificaciones.exito(
          `${resultado.matriculasCreadas + resultado.matriculasActualizadas} matricula(s) cargadas`,
          resultado.resumen,
        );
      },
      error: (error: ErrorApi) => {
        this.subiendo.set(false);
        this.notificaciones.error(error.mensaje ?? 'No se pudo cargar el archivo');
      },
    });
  }

  protected limpiar(): void {
    this.archivo.set(null);
    this.resultado.set(null);
    this.errorArchivo.set('');
  }

  protected tamano(archivo: File): string {
    const kb = archivo.size / 1024;
    return kb < 1024 ? `${kb.toFixed(0)} KB` : `${(kb / 1024).toFixed(1)} MB`;
  }
}
