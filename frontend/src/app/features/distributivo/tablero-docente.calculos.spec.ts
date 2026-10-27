import type { DocenteResumen, FilaSplitCarrera } from '@domain/modelos';

import {
  agregarSplit,
  alertasDocente,
  cantidadDeFunciones,
  claveDedicacion,
  cumpleFiltroDocente,
  cumpleFiltroSplit,
  esTitular,
  etcDe,
  FILTROS_VACIOS,
  gpill,
  ipill,
  mediana,
  movimientoDePersonas,
  movimientoPorFacultad,
  pill3,
  plantaDe,
  porcentajeTC,
  ratioPill,
  tcPill,
  tcQueFaltanPara,
  topeDa,
  topeH,
} from './tablero-docente.calculos';

function docente(datos: Partial<DocenteResumen> & { readonly docenteId: string }): DocenteResumen {
  return {
    identificacion: datos.docenteId,
    nombreCompleto: 'DOCENTE DE PRUEBA',
    facultadCodigo: 'FCII',
    facultadNombre: 'Ingeniería e Industrias',
    carreras: 'SISTEMAS',
    sedes: 'SEDE QUITO',
    niveles: ['Grado'],
    titularidad: 'TITULAR',
    categoria: 'AUXILIAR',
    dedicacion: 'TIEMPO COMPLETO',
    relacionLaboral: 'Dependencia Laboral',
    cargoDirectivo: '',
    da: 10,
    d: 20,
    i: 10,
    v: 0,
    g: 10,
    tot: 40,
    esTecnicoDocente: false,
    esDirectivo: false,
    esValido: true,
    estadoValidacion: 'OK',
    ...datos,
  };
}

function filaSplit(datos: Partial<FilaSplitCarrera> & { readonly docenteId: string }): FilaSplitCarrera {
  return {
    facultadCodigo: 'FCII',
    facultadNombre: 'Ingeniería e Industrias',
    carrera: 'SISTEMAS',
    carreraId: 'carrera-sistemas',
    sede: 'SEDE QUITO',
    nivel: 'Grado',
    dedicacion: 'TIEMPO COMPLETO',
    titularidad: 'TITULAR',
    categoria: 'AUXILIAR',
    da: 10,
    d: 20,
    i: 10,
    v: 0,
    g: 10,
    tot: 40,
    esTecnicoDocente: false,
    ...datos,
  };
}

describe('claveDedicacion', () => {
  it('normaliza el texto del catalogo a TC/MT/TP/NA', () => {
    expect(claveDedicacion('TIEMPO COMPLETO')).toBe('TC');
    expect(claveDedicacion('MEDIO TIEMPO')).toBe('MT');
    expect(claveDedicacion('TIEMPO PARCIAL')).toBe('TP');
    expect(claveDedicacion('')).toBe('NA');
    expect(claveDedicacion('OTRA COSA')).toBe('NA');
  });
});

describe('esTitular', () => {
  it('es true solo si el texto empieza con TITULAR', () => {
    expect(esTitular('TITULAR')).toBeTrue();
    expect(esTitular('TITULAR AUXILIAR')).toBeTrue();
    expect(esTitular('NO TITULAR')).toBeFalse();
    expect(esTitular('')).toBeFalse();
  });
});

describe('topeDa y topeH', () => {
  it('TC titular tiene 20h de Da y no titular 22h', () => {
    expect(topeDa('TC', true)).toBe(20);
    expect(topeDa('TC', false)).toBe(22);
  });
  it('MT y TP tienen un tope fijo de Da, sin importar la titularidad', () => {
    expect(topeDa('MT', true)).toBe(12);
    expect(topeDa('TP', false)).toBe(11);
  });
  it('NA no tiene tope de Da', () => {
    expect(topeDa('NA', true)).toBe(0);
  });
  it('el tope de horas totales es 40/20/19.99/40', () => {
    expect(topeH('TC')).toBe(40);
    expect(topeH('MT')).toBe(20);
    expect(topeH('TP')).toBe(19.99);
    expect(topeH('NA')).toBe(40);
  });
});

describe('alertasDocente', () => {
  it('marca a un TC que supera el tope de horas', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', tot: 41 });
    expect(alertasDocente(d)).toContain(jasmine.objectContaining({ nivel: 'bad' }));
  });

  it('marca a un TP con 20 horas o mas con un texto distinto al de los demas', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO PARCIAL', tot: 20.5, da: 10 });
    const alertas = alertasDocente(d);
    expect(alertas.some((a) => a.texto === 'TP con 20 h o más')).toBeTrue();
  });

  it('marca Da sobre el tope', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', da: 25, tot: 40 });
    expect(alertasDocente(d).some((a) => a.texto.startsWith('Da sobre el tope'))).toBeTrue();
  });

  it('un TC o MT sin horas de clase que no es tecnico docente trae advertencia', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', da: 0, esTecnicoDocente: false });
    expect(alertas_de(d)).toContain('Sin horas de clase');
  });

  it('un tecnico docente sin horas de clase no trae esa advertencia', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', da: 0, esTecnicoDocente: true });
    expect(alertas_de(d)).not.toContain('Sin horas de clase');
  });

  it('un TC con menos de 40h trae advertencia de carga incompleta', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', tot: 35, da: 10 });
    expect(alertas_de(d).some((t) => t.startsWith('TC con'))).toBeTrue();
  });

  it('un docente sin problemas no trae alertas', () => {
    const d = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', tot: 40, da: 10 });
    expect(alertasDocente(d)).toEqual([]);
  });

  function alertas_de(d: DocenteResumen): readonly string[] {
    return alertasDocente(d).map((a) => a.texto);
  }
});

describe('etcDe', () => {
  it('TC vale 1 y MT vale 0.5, sin importar las horas', () => {
    expect(etcDe({ dedicacion: 'TIEMPO COMPLETO', tot: 10 })).toBe(1);
    expect(etcDe({ dedicacion: 'MEDIO TIEMPO', tot: 5 })).toBe(0.5);
  });
  it('TP y NA valen horas/40, con tope en 40', () => {
    expect(etcDe({ dedicacion: 'TIEMPO PARCIAL', tot: 20 })).toBe(0.5);
    expect(etcDe({ dedicacion: 'TIEMPO PARCIAL', tot: 80 })).toBe(1);
  });
});

describe('semaforos', () => {
  it('pill3 compara contra el tope agregado de Da', () => {
    expect(pill3(1.5)).toBe('bad');
    expect(pill3(0.9)).toBe('ok');
    expect(pill3(0.6)).toBe('warn');
    expect(pill3(0.1)).toBe('bad');
  });
  it('gpill marca bad sobre 25% de gestion', () => {
    expect(gpill(0.3)).toBe('bad');
    expect(gpill(0.2)).toBe('warn');
    expect(gpill(0.1)).toBe('ok');
  });
  it('ipill exige al menos 6% de investigacion para estar ok', () => {
    expect(ipill(0.07)).toBe('ok');
    expect(ipill(0.04)).toBe('warn');
    expect(ipill(0.01)).toBe('bad');
  });
  it('tcPill sigue el art. 109 LOES: 50% minimo, 60% optimo', () => {
    expect(tcPill(0.65)).toBe('ok');
    expect(tcPill(0.55)).toBe('warn');
    expect(tcPill(0.3)).toBe('bad');
  });
  it('ratioPill marca posible exceso bajo 15 y sobrecarga sobre 30', () => {
    expect(ratioPill(10)).toBe('warn');
    expect(ratioPill(20)).toBe('ok');
    expect(ratioPill(35)).toBe('bad');
  });
});

describe('cumpleFiltroDocente', () => {
  it('excluye a quien no es valido', () => {
    const d = docente({ docenteId: '1', esValido: false });
    expect(cumpleFiltroDocente(d, FILTROS_VACIOS)).toBeFalse();
  });

  it('excluye a los tecnicos docentes salvo que se pida incluirlos', () => {
    const d = docente({ docenteId: '1', esTecnicoDocente: true });
    expect(cumpleFiltroDocente(d, FILTROS_VACIOS)).toBeFalse();
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, incluirTecnicos: true })).toBeTrue();
  });

  it('filtra por facultad, nivel y dedicacion segun los atributos principales', () => {
    const d = docente({ docenteId: '1', facultadCodigo: 'FAU', niveles: ['Grado', 'Posgrado'] });
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, facultadCodigo: 'FCII' })).toBeFalse();
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, facultadCodigo: 'FAU' })).toBeTrue();
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, nivel: 'Posgrado' })).toBeTrue();
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, nivel: 'Tecnología' })).toBeFalse();
  });

  it('filtra por titularidad', () => {
    const titular = docente({ docenteId: '1', titularidad: 'TITULAR' });
    const noTitular = docente({ docenteId: '2', titularidad: 'NO TITULAR' });
    expect(cumpleFiltroDocente(titular, { ...FILTROS_VACIOS, titularidad: 'titular' })).toBeTrue();
    expect(cumpleFiltroDocente(noTitular, { ...FILTROS_VACIOS, titularidad: 'titular' })).toBeFalse();
  });

  it('no excluye a los directivos salvo que se pida excluirlos', () => {
    const d = docente({ docenteId: '1', esDirectivo: true });
    expect(cumpleFiltroDocente(d, FILTROS_VACIOS)).toBeTrue();
    expect(cumpleFiltroDocente(d, { ...FILTROS_VACIOS, excluirDirectivos: true })).toBeFalse();
  });
});

describe('cumpleFiltroSplit', () => {
  it('se apoya en el filtro base del docente dueno, no de la fila', () => {
    const doc = docente({ docenteId: '1', esTecnicoDocente: true });
    const fila = filaSplit({ docenteId: '1' });
    expect(cumpleFiltroSplit(fila, doc, FILTROS_VACIOS)).toBeFalse();
    expect(cumpleFiltroSplit(fila, doc, { ...FILTROS_VACIOS, incluirTecnicos: true })).toBeTrue();
  });

  it('filtra facultad/nivel/dedicacion por la fila, no por el docente', () => {
    const doc = docente({ docenteId: '1', facultadCodigo: 'FCII' });
    const filaOtraFacultad = filaSplit({ docenteId: '1', facultadCodigo: 'FAU' });
    expect(
      cumpleFiltroSplit(filaOtraFacultad, doc, { ...FILTROS_VACIOS, facultadCodigo: 'FAU' }),
    ).toBeTrue();
    expect(
      cumpleFiltroSplit(filaOtraFacultad, doc, { ...FILTROS_VACIOS, facultadCodigo: 'FCII' }),
    ).toBeFalse();
  });

  it('sin el docente dueno, la fila no cuenta', () => {
    const fila = filaSplit({ docenteId: '1' });
    expect(cumpleFiltroSplit(fila, undefined, FILTROS_VACIOS)).toBeFalse();
  });

  it('excluye las filas del docente directivo, igual que con tecnicos', () => {
    const doc = docente({ docenteId: '1', esDirectivo: true });
    const fila = filaSplit({ docenteId: '1' });
    expect(cumpleFiltroSplit(fila, doc, { ...FILTROS_VACIOS, excluirDirectivos: true })).toBeFalse();
    expect(cumpleFiltroSplit(fila, doc, FILTROS_VACIOS)).toBeTrue();
  });
});

describe('agregarSplit', () => {
  it('suma las horas y el tope de Da de los docentes presentes, sin repetir', () => {
    const doc1 = docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO', titularidad: 'TITULAR' });
    const doc2 = docente({ docenteId: '2', dedicacion: 'TIEMPO PARCIAL' });
    const docentesPorId = new Map([
      ['1', doc1],
      ['2', doc2],
    ]);
    const filas = [
      filaSplit({ docenteId: '1', da: 10, tot: 30 }),
      filaSplit({ docenteId: '1', da: 2, tot: 10 }),
      filaSplit({ docenteId: '2', da: 5, tot: 11 }),
    ];
    const agregado = agregarSplit(filas, docentesPorId);
    expect(agregado.docentes).toBe(2);
    expect(agregado.da).toBe(17);
    expect(agregado.tot).toBe(51);
    // Tope de Da: 20 (TC titular) + 11 (TP) = 31, una vez por docente.
    expect(agregado.topeDaTotal).toBe(31);
    expect(agregado.porDocente.get('1')).toEqual({ da: 12, tot: 40, g: 20 });
  });
});

describe('movimientoPorFacultad y movimientoDePersonas', () => {
  const actual = [
    docente({ docenteId: '1', facultadCodigo: 'FCII', facultadNombre: 'FCII' }),
    docente({ docenteId: '3', facultadCodigo: 'FCII', facultadNombre: 'FCII' }),
  ];
  const anterior = [
    docente({ docenteId: '1', facultadCodigo: 'FCII', facultadNombre: 'FCII' }),
    docente({ docenteId: '2', facultadCodigo: 'FCII', facultadNombre: 'FCII' }),
  ];

  it('cuenta quien entra y quien sale globalmente', () => {
    const { entran, salen } = movimientoDePersonas(actual, anterior);
    expect(entran.map((d) => d.docenteId)).toEqual(['3']);
    expect(salen.map((d) => d.docenteId)).toEqual(['2']);
  });

  it('reparte el movimiento por facultad', () => {
    const filas = movimientoPorFacultad(actual, anterior);
    expect(filas).toEqual([
      { codigo: 'FCII', nombre: 'FCII', anterior: 2, actual: 2, entran: 1, salen: 1 },
    ]);
  });
});

describe('porcentajeTC', () => {
  it('es la proporcion de TC sobre el total', () => {
    const lista = [
      docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO' }),
      docente({ docenteId: '2', dedicacion: 'TIEMPO PARCIAL' }),
    ];
    expect(porcentajeTC(lista)).toBe(0.5);
    expect(porcentajeTC([])).toBe(0);
  });
});

describe('mediana', () => {
  it('promedia los dos centrales en listas pares', () => {
    expect(mediana([1, 2, 3, 4])).toBe(2.5);
  });
  it('toma el central en listas impares', () => {
    expect(mediana([5, 1, 3])).toBe(3);
  });
  it('es 0 para una lista vacia', () => {
    expect(mediana([])).toBe(0);
  });
});

describe('plantaDe y tcQueFaltanPara', () => {
  it('cuenta TC, MT y TP, y suma el ETC de todos', () => {
    const lista = [
      docente({ docenteId: '1', dedicacion: 'TIEMPO COMPLETO' }),
      docente({ docenteId: '2', dedicacion: 'MEDIO TIEMPO' }),
      docente({ docenteId: '3', dedicacion: 'TIEMPO PARCIAL', tot: 20 }),
    ];
    const planta = plantaDe(lista);
    expect(planta).toEqual({ docentes: 3, tc: 1, mt: 1, tp: 1, etc: 1 + 0.5 + 0.5 });
  });

  it('calcula cuantos TC faltan para una razon, sin bajar de cero', () => {
    // 10 docentes, 4 TC: para 50% faltan 1; para 60% faltan 2.
    expect(tcQueFaltanPara(0.5, 10, 4)).toBe(1);
    expect(tcQueFaltanPara(0.6, 10, 4)).toBe(2);
    // Ya cumple de sobra: no "sobran" TC negativos.
    expect(tcQueFaltanPara(0.5, 10, 9)).toBe(0);
  });
});

describe('cantidadDeFunciones', () => {
  it('cuenta D, I, V y G con horas mayores a cero', () => {
    const d = docente({ docenteId: '1', d: 10, i: 0, v: 5, g: 0 });
    expect(cantidadDeFunciones(d)).toBe(2);
    const completo = docente({ docenteId: '2', d: 10, i: 1, v: 1, g: 1 });
    expect(cantidadDeFunciones(completo)).toBe(4);
  });
});
