import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { Conteo, PuntoSerie } from '@domain/modelos';

/**
 * Graficos en SVG generado a mano.
 *
 * Se evita deliberadamente una libreria de graficos: estos tres tipos son
 * simples, y una dependencia externa costaria cientos de kilobytes, un tema
 * propio que no encaja con el resto y una superficie de actualizacion mas.
 *
 * La paleta se toma de las variables CSS, asi que los graficos siguen el tema
 * claro u oscuro sin codigo adicional.
 */

const PALETA = [
  'var(--azul-800)',
  'var(--azul-600)',
  '#4d7cbf',
  '#6e97d1',
  '#8fb2e0',
  '#b0cced',
  '#9a6400',
  '#1b7f4b',
];

// ---------------------------------------------------------------------------
@Component({
  selector: 'ute-grafico-barras',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (datos().length === 0) {
      <p class="vacio-grafico texto-sm texto-tenue">Sin datos para mostrar</p>
    } @else {
      <ul class="barras" [attr.aria-label]="titulo()">
        @for (dato of datos(); track dato.etiqueta; let i = $index) {
          <li class="barra-item">
            <div class="barra-item__cabecera">
              <span class="barra-item__etiqueta" [title]="dato.etiqueta">
                {{ dato.etiqueta }}
              </span>
              <span class="barra-item__valor mono">{{ dato.valor }}</span>
            </div>
            <div class="barra">
              <div
                class="barra__relleno"
                [style.width.%]="ancho(dato)"
                [style.background]="color(i)"
              ></div>
            </div>
          </li>
        }
      </ul>
    }
  `,
  styles: [
    `
      .barras { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.7rem; }
      .barra-item__cabecera {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.25rem;
        font-size: 0.8rem;
      }
      .barra-item__etiqueta {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--texto-suave);
      }
      .barra-item__valor { font-weight: 600; flex-shrink: 0; }
      .vacio-grafico { text-align: center; padding: 1.5rem 0; margin: 0; }
    `,
  ],
})
export class GraficoBarrasComponent {
  readonly datos = input.required<readonly Conteo[]>();
  readonly titulo = input('Distribucion');

  private readonly maximo = computed(() =>
    Math.max(1, ...this.datos().map((d) => d.valor)),
  );

  protected ancho(dato: Conteo): number {
    return (dato.valor / this.maximo()) * 100;
  }

  protected color(indice: number): string {
    return PALETA[indice % PALETA.length]!;
  }
}

/** Una categoria del grafico de barras agrupadas (una facultad), con sus
 * valores por serie (un estado). Las series ausentes en `valores` valen 0. */
export interface SerieAgrupada {
  readonly etiqueta: string;
  readonly valores: Readonly<Record<string, number>>;
}

// ---------------------------------------------------------------------------
@Component({
  selector: 'ute-grafico-barras-agrupadas',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (grupos().length === 0 || series().length === 0) {
      <p class="vacio-grafico texto-sm texto-tenue">Sin datos para mostrar</p>
    } @else {
      <div [attr.aria-label]="titulo()">
        <div class="lienzo">
          @for (linea of lineasGuia; track linea) {
            <div class="lienzo__guia" [style.bottom.%]="linea"></div>
          }
          @for (grupo of grupos(); track grupo.etiqueta) {
            <div class="grupo">
              <div class="grupo__barras">
                @for (serie of series(); track serie; let i = $index) {
                  <div
                    class="grupo__barra"
                    [style.height.%]="altura(grupo, serie)"
                    [style.background]="color(i)"
                  >
                    <span class="grupo__globo">{{ serie }}: {{ valor(grupo, serie) }}</span>
                  </div>
                }
              </div>
              <span class="grupo__etiqueta" [title]="grupo.etiqueta">{{ grupo.etiqueta }}</span>
            </div>
          }
        </div>

        <ul class="leyenda leyenda--horizontal">
          @for (serie of series(); track serie; let i = $index) {
            <li class="leyenda__item">
              <span class="leyenda__punto" [style.background]="color(i)"></span>
              <span class="leyenda__etiqueta" [title]="serie">{{ serie }}</span>
            </li>
          }
        </ul>
      </div>
    }
  `,
  styles: [
    `
      .lienzo {
        display: flex;
        align-items: flex-end;
        gap: 1.5rem;
        height: 220px;
        padding: 0 0.25rem;
        position: relative;
        border-bottom: 1px solid var(--borde);
      }
      .lienzo__guia {
        position: absolute;
        left: 0;
        right: 0;
        border-top: 1px dashed var(--borde);
      }
      .grupo {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
        min-width: 0;
        height: 100%;
        justify-content: flex-end;
      }
      .grupo__barras {
        display: flex;
        align-items: flex-end;
        justify-content: center;
        gap: 3px;
        width: 100%;
        height: 100%;
      }
      .grupo__barra {
        position: relative;
        width: 12px;
        min-height: 2px;
        border-radius: 2px 2px 0 0;
      }
      .grupo__globo {
        position: absolute;
        bottom: calc(100% + 4px);
        left: 50%;
        transform: translateX(-50%);
        white-space: nowrap;
        font-size: 0.7rem;
        background: var(--superficie-elevada, var(--superficie));
        border: 1px solid var(--borde);
        border-radius: 4px;
        padding: 0.15rem 0.4rem;
        opacity: 0;
        pointer-events: none;
        transition: opacity 150ms ease;
        z-index: 1;
      }
      .grupo__barra:hover .grupo__globo { opacity: 1; }
      .grupo__etiqueta {
        font-size: 0.72rem;
        color: var(--texto-suave);
        text-align: center;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 100%;
      }
      .leyenda--horizontal {
        list-style: none;
        margin: 0.75rem 0 0;
        padding: 0;
        display: flex;
        flex-wrap: wrap;
        gap: 0.9rem;
      }
      .leyenda__item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; }
      .leyenda__punto { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
      .leyenda__etiqueta { color: var(--texto-suave); max-width: 14rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .vacio-grafico { text-align: center; padding: 1.5rem 0; margin: 0; }
    `,
  ],
})
export class GraficoBarrasAgrupadasComponent {
  readonly grupos = input.required<readonly SerieAgrupada[]>();
  /** Orden y color de las barras dentro de cada grupo. */
  readonly series = input.required<readonly string[]>();
  readonly titulo = input('Distribucion');

  protected readonly lineasGuia = [25, 50, 75];

  private readonly maximo = computed(() =>
    Math.max(
      1,
      ...this.grupos().flatMap((g) => this.series().map((s) => g.valores[s] ?? 0)),
    ),
  );

  protected valor(grupo: SerieAgrupada, serie: string): number {
    return grupo.valores[serie] ?? 0;
  }

  protected altura(grupo: SerieAgrupada, serie: string): number {
    return (this.valor(grupo, serie) / this.maximo()) * 100;
  }

  protected color(indice: number): string {
    return PALETA[indice % PALETA.length]!;
  }
}

// ---------------------------------------------------------------------------
@Component({
  selector: 'ute-grafico-anillo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (total() === 0) {
      <p class="vacio-grafico texto-sm texto-tenue">Sin datos para mostrar</p>
    } @else {
      <div class="anillo-envoltura">
        <svg viewBox="0 0 42 42" class="anillo" role="img" [attr.aria-label]="titulo()">
          <circle class="anillo__fondo" cx="21" cy="21" r="15.9" />
          @for (segmento of segmentos(); track segmento.etiqueta) {
            <circle
              cx="21"
              cy="21"
              r="15.9"
              class="anillo__segmento"
              [attr.stroke]="segmento.color"
              [attr.stroke-dasharray]="segmento.longitud + ' ' + (100 - segmento.longitud)"
              [attr.stroke-dashoffset]="segmento.desfase"
            >
              <title>{{ segmento.etiqueta }}: {{ segmento.valor }}</title>
            </circle>
          }
          <text x="21" y="20" class="anillo__total">{{ total() }}</text>
          <text x="21" y="25" class="anillo__leyenda">{{ unidad() }}</text>
        </svg>

        <ul class="leyenda">
          @for (segmento of segmentos(); track segmento.etiqueta) {
            <li class="leyenda__item">
              <span class="leyenda__punto" [style.background]="segmento.color"></span>
              <span class="leyenda__etiqueta" [title]="segmento.etiqueta">
                {{ segmento.etiqueta }}
              </span>
              <span class="leyenda__valor mono">{{ segmento.valor }}</span>
            </li>
          }
        </ul>
      </div>
    }
  `,
  styles: [
    `
      .anillo-envoltura { display: flex; align-items: center; gap: 1.25rem; flex-wrap: wrap; }
      .anillo { width: 132px; height: 132px; flex-shrink: 0; transform: rotate(-90deg); }
      .anillo__fondo { fill: none; stroke: var(--borde); stroke-width: 3.4; }
      .anillo__segmento {
        fill: none;
        stroke-width: 3.4;
        transition: stroke-dasharray 400ms ease;
      }
      .anillo__total {
        transform: rotate(90deg);
        transform-origin: center;
        text-anchor: middle;
        font-size: 0.42rem;
        font-weight: 700;
        fill: var(--texto);
      }
      .anillo__leyenda {
        transform: rotate(90deg);
        transform-origin: center;
        text-anchor: middle;
        font-size: 0.16rem;
        fill: var(--texto-tenue);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }
      .leyenda { list-style: none; margin: 0; padding: 0; flex: 1; min-width: 11rem; }
      .leyenda__item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.2rem 0;
        font-size: 0.8rem;
      }
      .leyenda__punto { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
      .leyenda__etiqueta {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--texto-suave);
      }
      .leyenda__valor { font-weight: 600; }
      .vacio-grafico { text-align: center; padding: 1.5rem 0; margin: 0; }
    `,
  ],
})
export class GraficoAnilloComponent {
  readonly datos = input.required<readonly Conteo[]>();
  readonly titulo = input('Distribucion');
  readonly unidad = input('total');

  protected readonly total = computed(() =>
    this.datos().reduce((suma, d) => suma + d.valor, 0),
  );

  /**
   * Segmentos del anillo.
   *
   * Se dibujan con `stroke-dasharray` sobre una circunferencia de 100 unidades
   * de perimetro: asi el largo de cada arco es literalmente su porcentaje, sin
   * trigonometria de por medio.
   */
  protected readonly segmentos = computed(() => {
    const total = this.total();
    if (total === 0) return [];

    let acumulado = 0;
    return this.datos().map((dato, indice) => {
      const longitud = (dato.valor / total) * 100;
      const segmento = {
        etiqueta: dato.etiqueta,
        valor: dato.valor,
        longitud,
        // El desfase corre en sentido inverso al trazo.
        desfase: 100 - acumulado,
        color: PALETA[indice % PALETA.length]!,
      };
      acumulado += longitud;
      return segmento;
    });
  });
}

// ---------------------------------------------------------------------------
@Component({
  selector: 'ute-grafico-linea',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (puntos().length < 2) {
      <p class="vacio-grafico texto-sm texto-tenue">
        Se necesitan al menos dos dias con actividad para trazar la tendencia
      </p>
    } @else {
      <svg
        [attr.viewBox]="'0 0 ' + ANCHO + ' ' + ALTO"
        class="linea"
        role="img"
        [attr.aria-label]="titulo()"
        preserveAspectRatio="none"
      >
        <!-- Rejilla de referencia -->
        @for (y of lineasGuia(); track y) {
          <line class="linea__guia" x1="0" [attr.y1]="y" [attr.x2]="ANCHO" [attr.y2]="y" />
        }

        <path class="linea__area" [attr.d]="area()" />
        <path class="linea__trazo" [attr.d]="trazo()" />

        @for (punto of coordenadas(); track punto.fecha) {
          <circle class="linea__punto" [attr.cx]="punto.x" [attr.cy]="punto.y" r="2.5">
            <title>{{ punto.fecha }}: {{ punto.valor }}</title>
          </circle>
        }
      </svg>

      <div class="linea__ejes texto-xs texto-tenue">
        <span>{{ primeraFecha() }}</span>
        <span>maximo: {{ maximo() }}</span>
        <span>{{ ultimaFecha() }}</span>
      </div>
    }
  `,
  styles: [
    `
      .linea { width: 100%; height: 150px; overflow: visible; }
      .linea__guia { stroke: var(--borde); stroke-width: 1; }
      .linea__trazo {
        fill: none;
        stroke: var(--azul-700);
        stroke-width: 2;
        stroke-linejoin: round;
        stroke-linecap: round;
        vector-effect: non-scaling-stroke;
      }
      .linea__area { fill: var(--azul-100); opacity: 0.55; }
      .linea__punto { fill: var(--azul-800); }
      .linea__ejes {
        display: flex;
        justify-content: space-between;
        margin-top: 0.5rem;
      }
      .vacio-grafico { text-align: center; padding: 1.5rem 0; margin: 0; }
    `,
  ],
})
export class GraficoLineaComponent {
  readonly puntos = input.required<readonly PuntoSerie[]>();
  readonly titulo = input('Tendencia');

  protected readonly ANCHO = 100;
  protected readonly ALTO = 40;

  protected readonly maximo = computed(() =>
    Math.max(1, ...this.puntos().map((p) => p.valor)),
  );

  protected readonly coordenadas = computed(() => {
    const lista = this.puntos();
    const maximo = this.maximo();
    const paso = lista.length > 1 ? this.ANCHO / (lista.length - 1) : 0;

    return lista.map((punto, indice) => ({
      fecha: punto.fecha,
      valor: punto.valor,
      x: indice * paso,
      // El eje Y del SVG crece hacia abajo: se invierte.
      y: this.ALTO - (punto.valor / maximo) * (this.ALTO - 4) - 2,
    }));
  });

  protected readonly trazo = computed(() =>
    this.coordenadas()
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
      .join(' '),
  );

  protected readonly area = computed(() => {
    const puntos = this.coordenadas();
    if (puntos.length < 2) return '';
    const primero = puntos[0]!;
    const ultimo = puntos[puntos.length - 1]!;
    return `${this.trazo()} L ${ultimo.x.toFixed(2)} ${this.ALTO} L ${primero.x.toFixed(2)} ${this.ALTO} Z`;
  });

  protected readonly lineasGuia = computed(() =>
    [0.25, 0.5, 0.75].map((fraccion) => (this.ALTO * fraccion).toFixed(1)),
  );

  protected readonly primeraFecha = computed(() => this.formatear(this.puntos()[0]?.fecha));
  protected readonly ultimaFecha = computed(() =>
    this.formatear(this.puntos()[this.puntos().length - 1]?.fecha),
  );

  private formatear(fecha: string | undefined): string {
    if (!fecha) return '';
    return new Date(`${fecha}T00:00:00`).toLocaleDateString('es-EC', {
      day: '2-digit',
      month: 'short',
    });
  }
}
