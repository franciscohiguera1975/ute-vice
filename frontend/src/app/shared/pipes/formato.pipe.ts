import { Pipe, type PipeTransform } from '@angular/core';

/**
 * Fecha y hora en formato local ecuatoriano.
 *
 * El backend trabaja en UTC; la conversion a hora local ocurre aqui, en el
 * borde. Mostrar UTC a un funcionario en Quito le haria leer las consultas de
 * la tarde como si fueran de la noche.
 */
@Pipe({ name: 'fechaLocal', standalone: true })
export class FechaLocalPipe implements PipeTransform {
  transform(valor: string | Date | null | undefined, conHora = false): string {
    if (!valor) return '—';
    const fecha = valor instanceof Date ? valor : new Date(valor);
    if (Number.isNaN(fecha.getTime())) return '—';

    return fecha.toLocaleString('es-EC', {
      timeZone: 'America/Guayaquil',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      ...(conHora ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
    });
  }
}

/** Tiempo transcurrido en lenguaje natural: "hace 3 dias". */
@Pipe({ name: 'desdeHace', standalone: true })
export class DesdeHacePipe implements PipeTransform {
  private static readonly UNIDADES: readonly [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ];

  transform(valor: string | Date | null | undefined): string {
    if (!valor) return 'nunca';
    const fecha = valor instanceof Date ? valor : new Date(valor);
    if (Number.isNaN(fecha.getTime())) return '—';

    const segundos = (fecha.getTime() - Date.now()) / 1000;
    const formateador = new Intl.RelativeTimeFormat('es', { numeric: 'auto' });

    for (const [unidad, factor] of DesdeHacePipe.UNIDADES) {
      if (Math.abs(segundos) >= factor) {
        return formateador.format(Math.round(segundos / factor), unidad);
      }
    }
    return 'hace un momento';
  }
}

/** Duracion en milisegundos, legible: "1,2 s". */
@Pipe({ name: 'duracion', standalone: true })
export class DuracionPipe implements PipeTransform {
  transform(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return '—';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1).replace('.', ',')} s`;
    return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`;
  }
}

/** Cedula enmascarada para pantallas de bajo privilegio: `17******65`. */
@Pipe({ name: 'cedulaEnmascarada', standalone: true })
export class CedulaEnmascaradaPipe implements PipeTransform {
  transform(cedula: string | null | undefined): string {
    if (!cedula || cedula.length < 4) return cedula ?? '—';
    return `${cedula.slice(0, 2)}${'*'.repeat(cedula.length - 4)}${cedula.slice(-2)}`;
  }
}
