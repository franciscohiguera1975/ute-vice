# Fase 21 · PFCSEE se integra en FCSEE

**Fecha:** 2026-09-17 · **Estado:** ✅

El sistema académico nuevo ya no distingue los posgrados de ciencias de la salud
como unidad aparte: sus docentes figuran bajo *Ciencias de la Salud Eugenio
Espejo*.

## Cómo se verificó

No por el nombre de la facultad, que cambia entre sistemas, sino **por cédula**
contra el distributivo oficial de 2026-1:

| Facultad | Docentes en el sistema | Aparecen en el archivo oficial | Bajo qué facultad |
|---|---|---|---|
| PFCSEE | 176 | 13 | **Ciencias de la Salud, el 100 %** |
| FO | 75 | 3 | Ciencias de la Salud, el 100 % |

La dirección es inequívoca. Lo que no alcanza es la **cobertura**: el export
oficial solo trae al 12 % de esos docentes, y a 171 de los 466 de FCSEE. Las
otras seis facultades están completas.

Eso descarta cargar el archivo tal cual —borraría 428 personas— pero **no
impide adoptar la estructura**, que es lo que hace esta fase.

## Qué cambia

**213 filas de 2026-1** pasan de `PFCSEE` a `FCSEE`, que queda con 732.

`PFCSEE` se marca **inactiva, no se elimina**: deja de ofrecerse en los
selectores y conserva sus **1.775 filas históricas**.

### Por qué solo desde 2026-1

El distributivo es un registro histórico. Reescribir 2020-2025 para que se
parezca a la estructura de 2026 haría irreproducibles los informes ya emitidos:
quien busque «PFCSEE 2024-2» debe seguir encontrándolo.

### Por qué FO no se toca

El catálogo de facultades del ERP **sí lista `FO — ODONTOLOGÍA`** como unidad
propia, aunque el distributivo de 2026-1 ponga odontología bajo FS. Hasta
aclarar esa contradicción, FO queda como está.

## La reversibilidad, y por qué costó

La facultad anterior **no se puede deducir después del cambio**: FCSEE ya tenía
filas con las mismas carreras —endodoncia, psiquiatría, odontología— cargadas por
otra vía.

```
FCSEE   ESPECIALIZACIÓN EN ENDODONCIA    15   ← carga parcial del 14-sep
PFCSEE  ESPECIALIZACIÓN EN ENDODONCIA    11   ← consolidado
```

Por eso la migración crea `distributivo_facultad_previa`, que guarda los
identificadores de las filas movidas. La vuelta atrás los lee y descarta la
tabla. Verificado: tras bajar, FCSEE vuelve a 519 y PFCSEE a 213.

La tabla queda además como constancia de qué filas pertenecieron a otra unidad
antes de la integración.

## Lo que sigue pendiente

- **428 docentes del bloque de salud** no están en el export oficial. Antes de
  borrar nada hay que confirmar si siguen dictando o si la migración del ERP no
  los trajo.
- **147 filas del archivo fusionan carrera o sede** en una celda y crearían 57
  carreras inexistentes. Se necesita el export desagregado.
- **Cuatro categorías duplicadas** de la carga parcial: `TITULAR AUXILIAR` (84),
  `TITULAR PRINCIPAL` (11), `TITULAR AGREGADO` (9), `TITULAR AUXILIAR 1` (1).
