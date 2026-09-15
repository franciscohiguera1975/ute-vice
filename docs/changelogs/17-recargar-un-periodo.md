# Fase 17 · Recargar un período sin perder lo enlazado

**Fecha:** 2026-09-14 · **Estado:** ✅

Cargar una corrección de un período ya cargado era imposible: la importación
chocaba con la clave natural en la primera fila que ya existía. La única salida
era vaciar el período antes —y con él, las materias enlazadas a cada fila—.

## El intento que falló

El primer enfoque fue calcular fuera qué filas ya existían, borrarlas y luego
importar. Se probó tres veces sobre una copia de producción y falló las tres,
cada vez por una normalización distinta:

| Intento | Qué se comparó | Por qué falló |
|---|---|---|
| 1.º | `sede.nombre` | La sede `MON` se llama «Monjas (Ricardo Hidalgo Ottolenghi)» |
| 2.º | `sede.codigo` | La cédula `17686345` se escribe distinto en el origen |
| 3.º | — | Un `if/else` mal parentizado dejaba pasar las filas fundidas |

Los tres habrían duplicado filas en producción en vez de actualizarlas. Los tres
los detuvo el ensayo sobre una copia del respaldo, no una prueba unitaria.

La lección no es «hay que comparar mejor». Es que **reproducir la clave natural
fuera del sistema obliga a repetir su normalización —cédulas, sedes, catálogos—
y basta equivocarse en una**.

## La solución

`reemplazar_muchas` delega el choque en PostgreSQL:

```sql
INSERT ... ON CONFLICT ON CONSTRAINT uq_distributivo_docente_pao_carrera_sede
DO UPDATE SET ...
RETURNING (xmax = 0) AS es_alta
```

La restricción **ya es** la clave natural, con `NULLS NOT DISTINCT` para las
filas sin sede. No hay comparación escrita a mano que pueda desviarse de ella.

`xmax = 0` distingue el alta del cambio: es el identificador de la transacción
que bloqueó la fila, y vale cero en una inserción limpia.

### Lo que esto salva

**Conserva el id de la fila.** Las materias cuelgan de él, así que sobreviven a
la recarga. Borrar e insertar habría perdido los 22.158 enlaces de la fase 15 y
habría obligado a recargarlos después.

Verificado en el ensayo: tras recargar 2026-1, `distributivo_asignaturas`
seguía con 22.158 filas exactas.

## Detalles que costaron

- **`VALUES` de varias filas exige las mismas columnas en todas.** Omitir
  `sede_id` en las dieciséis filas que no la tienen no compila. Los registros se
  construyen con un juego fijo de claves.
- **`onupdate` no se dispara en un upsert del núcleo.** `actualizado_en` se pone
  a mano con `func.now()`, o la fila quedaría fechada el día que se creó.

## Uso

```bash
python -m app.cli importar-distributivo <archivo.xlsx> --reemplazar
```

Sin la bandera, el comportamiento es el de siempre: solo inserta.

## Resultado sobre 2026-1

| | |
|---|---|
| Filas leídas | 824 de 827 (tres con `IDENTIFICACION = N/A`) |
| Creadas | 57 |
| Actualizadas | 758 |
| Consolidadas | 9 (misma clave natural repetida en el origen) |
| Enlaces de materias | 22.158, **intactos** |

Quedaron fuera las **147 filas del archivo que funden varias carreras o sedes
en una celda**; su reparto de horas no se puede reconstruir. Ver
`analisis_actualizado_2026_1.md`.

## Lo que hay que revisar a mano

16 docentes de 1.327 quedan con horas implausibles. Ninguno lo causa la carga:

- **1 con 407,2 h** — error del archivo de origen (cédula 1712434206)
- **6 con exactamente 80 h** — filas duplicadas en el origen que el importador
  suma, como está documentado que hace
- **1 con 66,5 h** — dicta en FCSEE y conserva filas en PFCSEE, porque el
  archivo no trae PFCSEE y sus filas viejas se mantienen
