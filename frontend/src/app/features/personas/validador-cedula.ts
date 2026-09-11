import type { AbstractControl, ValidationErrors } from '@angular/forms';

/**
 * Validador de cedula ecuatoriana.
 *
 * Replica el algoritmo de modulo 10 que aplica el backend. Duplicar la regla
 * es aceptable —y deseable— aqui: el backend sigue siendo la autoridad, pero
 * validar en el navegador evita un viaje al servidor para decirle al usuario
 * algo que se sabe al instante.
 */
const COEFICIENTES = [2, 1, 2, 1, 2, 1, 2, 1, 2] as const;
const PROVINCIAS_VALIDAS = new Set([...Array.from({ length: 24 }, (_, i) => i + 1), 30]);

export function validadorCedula(control: AbstractControl): ValidationErrors | null {
  const valor = String(control.value ?? '').replace(/[\s\-.]/g, '');
  if (!valor) return null; // la obligatoriedad la comprueba `Validators.required`

  if (!/^\d+$/.test(valor)) {
    return { cedulaInvalida: 'La cedula solo admite digitos' };
  }
  if (valor.length !== 10) {
    return { cedulaInvalida: `La cedula debe tener 10 digitos (tiene ${valor.length})` };
  }
  if (!PROVINCIAS_VALIDAS.has(Number(valor.slice(0, 2)))) {
    return { cedulaInvalida: `Codigo de provincia invalido: ${valor.slice(0, 2)}` };
  }
  // El tercer digito >= 6 corresponde a entidades publicas y sociedades.
  if (Number(valor[2]) >= 6) {
    return { cedulaInvalida: 'No corresponde a una cedula de persona natural' };
  }

  let total = 0;
  for (let i = 0; i < 9; i++) {
    const producto = Number(valor[i]) * COEFICIENTES[i]!;
    total += producto >= 10 ? producto - 9 : producto;
  }
  const verificador = (10 - (total % 10)) % 10;

  return verificador === Number(valor[9])
    ? null
    : { cedulaInvalida: 'El digito verificador no es correcto' };
}
