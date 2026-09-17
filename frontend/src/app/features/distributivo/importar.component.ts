import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import type { ErrorApi, ResultadoCargaPao } from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';

/** Extensiones que acepta el lector del backend. */
const EXTENSIONES = ['.xls', '.xlsx', '.xlsm'];

/** Mismo tope que el endpoint. Comprobarlo aqui evita una subida inutil. */
const TOPE_MB = 25;

const PATRON_SEMESTRE = /^\d{4}-[12]$/;

/**
 * Carga de un distributivo exportado por el sistema academico.
 *
 * El archivo **no dice a que semestre pertenece**, asi que lo indica quien
 * importa. Un archivo produce hasta tres periodos: a cual va cada fila lo
 * decide su facultad —tecnologia, grado o posgrado—, igual que en la carga por
 * linea de comandos.
 */
@Component({
  selector: 'ute-importar-pao',
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './importar.component.html',
  styleUrl: './importar.component.scss',
})
export class ImportarPaoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly EXTENSIONES = EXTENSIONES;
  protected readonly TOPE_MB = TOPE_MB;

  protected readonly archivo = signal<File | null>(null);
  protected readonly semestre = signal('');
  protected readonly interciclo = signal(false);
  protected readonly actualizarExistentes = signal(true);
  protected readonly hoja = signal('');

  protected readonly subiendo = signal(false);
  protected readonly resultado = signal<ResultadoCargaPao | null>(null);
  protected readonly errorArchivo = signal('');

  /** Solo se muestran las primeras; el resto se resume en una linea. */
  protected readonly TOPE_LISTA = 15;

  protected readonly semestreValido = computed(() => PATRON_SEMESTRE.test(this.semestre().trim()));

  protected readonly puedeSubir = computed(
    () => this.archivo() !== null && this.semestreValido() && !this.subiendo(),
  );

  protected readonly catalogosCreados = computed(() =>
    Object.entries(this.resultado()?.elementosCatalogoCreados ?? {}).sort(
      (a, b) => b[1] - a[1],
    ),
  );

  protected readonly filasTocadas = computed(() => {
    const r = this.resultado();
    return r ? r.filasCreadas + r.filasActualizadas : 0;
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
    // El nombre del archivo suele traer el semestre —`PAO_2026_2.xls`—. Se
    // propone, pero se deja editable: es una conjetura, no un dato del archivo.
    if (!this.semestre()) {
      const encontrado = /(\d{4})[_-]([12])(?!\d)/.exec(elegido.name);
      if (encontrado) this.semestre.set(`${encontrado[1]}-${encontrado[2]}`);
      if (/interciclo/i.test(elegido.name)) this.interciclo.set(true);
    }
  }

  protected subir(): void {
    const elegido = this.archivo();
    if (!elegido || !this.semestreValido()) return;

    this.subiendo.set(true);
    this.resultado.set(null);

    this.repositorio
      .cargarPao({
        archivo: elegido,
        semestre: this.semestre().trim(),
        interciclo: this.interciclo(),
        actualizarExistentes: this.actualizarExistentes(),
        hoja: this.hoja().trim() || undefined,
      })
      .subscribe({
        next: (resultado) => {
          this.resultado.set(resultado);
          this.subiendo.set(false);
          this.notificaciones.exito(
            `${resultado.filasCreadas + resultado.filasActualizadas} fila(s) cargadas`,
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
    this.semestre.set('');
    this.interciclo.set(false);
    this.hoja.set('');
  }

  protected tamano(archivo: File): string {
    const kb = archivo.size / 1024;
    return kb < 1024 ? `${kb.toFixed(0)} KB` : `${(kb / 1024).toFixed(1)} MB`;
  }
}
