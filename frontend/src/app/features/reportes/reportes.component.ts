import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DescargaService } from '@core/descarga.service';
import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_TITULO,
  ETIQUETAS_NIVEL,
  ETIQUETAS_VINCULACION,
  EstadoTitulo,
  FormatoReporte,
  NivelTitulo,
  TipoVinculacion,
  type ErrorApi,
} from '@domain/modelos';
import { RepositorioReportes } from '@domain/puertos';

type TipoReporte = 'personas' | 'titulos' | 'consultas';

@Component({
  selector: 'ute-reportes',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reportes.component.html',
  styleUrl: './reportes.component.scss',
})
export class ReportesComponent {
  private readonly repositorio = inject(RepositorioReportes);
  private readonly descarga = inject(DescargaService);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly ETIQUETAS_VINCULACION = ETIQUETAS_VINCULACION;
  protected readonly ETIQUETAS_NIVEL = ETIQUETAS_NIVEL;
  protected readonly ETIQUETAS_ESTADO_TITULO = ETIQUETAS_ESTADO_TITULO;
  protected readonly vinculaciones = Object.values(TipoVinculacion);
  protected readonly niveles = Object.values(NivelTitulo);
  protected readonly estadosTitulo = Object.values(EstadoTitulo);

  protected readonly formatos: readonly { valor: FormatoReporte; etiqueta: string; nota: string }[] =
    [
      {
        valor: FormatoReporte.XLSX,
        etiqueta: 'Excel',
        nota: 'Numeros y fechas con su tipo nativo: se pueden ordenar y sumar',
      },
      {
        valor: FormatoReporte.CSV,
        etiqueta: 'CSV',
        nota: 'Texto delimitado, para cargar en otro sistema',
      },
      {
        valor: FormatoReporte.PDF,
        etiqueta: 'PDF',
        nota: 'Documento para imprimir o adjuntar; se limita a 5.000 filas',
      },
    ];

  protected readonly tipo = signal<TipoReporte>('personas');
  protected readonly formato = signal<FormatoReporte>(FormatoReporte.XLSX);
  protected readonly generando = signal(false);

  // --- Filtros de personas ---
  protected readonly unidad = signal('');
  protected readonly vinculacion = signal<TipoVinculacion | ''>('');
  protected readonly soloActivos = signal(true);
  protected readonly conTitulos = signal<'' | 'true' | 'false'>('');
  protected readonly incluirTitulos = signal(false);

  // --- Filtros de titulos ---
  protected readonly nivel = signal<NivelTitulo | ''>('');
  protected readonly estadoTitulo = signal<EstadoTitulo | ''>('');
  protected readonly institucion = signal('');

  // --- Filtros de consultas ---
  protected readonly desde = signal('');
  protected readonly hasta = signal('');
  protected readonly soloErrores = signal(false);
  protected readonly soloConCambios = signal(false);

  protected generar(): void {
    this.generando.set(true);

    const alTerminar = {
      next: (archivo: { nombre: string; contenido: Blob; tipoMime: string }) => {
        this.generando.set(false);
        this.descarga.guardar(archivo);
        this.notificaciones.exito(
          'Reporte generado',
          `${archivo.nombre} · ${this.tamano(archivo.contenido.size)}`,
        );
      },
      error: (error: ErrorApi) => {
        this.generando.set(false);

        // 413 significa que el resultado excede el maximo permitido: la salida
        // es filtrar mas, no reintentar.
        if (error.estado === 413) {
          this.notificaciones.error(
            'El reporte es demasiado grande',
            'Aplique filtros adicionales para acotar el resultado.',
          );
          return;
        }
        this.notificaciones.error('No fue posible generar el reporte', error.mensaje);
      },
    };

    switch (this.tipo()) {
      case 'personas':
        this.repositorio
          .personas(
            this.formato(),
            {
              unidad: this.unidad().trim() || undefined,
              tipoVinculacion: this.vinculacion() || undefined,
              activo: this.soloActivos() ? true : undefined,
              conTitulos: this.conTitulos() === '' ? undefined : this.conTitulos() === 'true',
            },
            this.incluirTitulos(),
          )
          .subscribe(alTerminar);
        break;

      case 'titulos':
        this.repositorio
          .titulos(this.formato(), {
            nivel: this.nivel() || undefined,
            estado: this.estadoTitulo() || undefined,
            institucion: this.institucion().trim() || undefined,
          })
          .subscribe(alTerminar);
        break;

      case 'consultas':
        this.repositorio
          .consultas(this.formato(), {
            desde: this.desde() || undefined,
            hasta: this.hasta() || undefined,
            soloErrores: this.soloErrores() || undefined,
            soloConCambios: this.soloConCambios() || undefined,
          })
          .subscribe(alTerminar);
        break;
    }
  }

  private tamano(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1).replace('.', ',')} KB`;
    return `${(bytes / 1_048_576).toFixed(1).replace('.', ',')} MB`;
  }
}
