# Fase 13 · Cada semestre son tres periodos academicos

**Fecha:** 2026-09-14 · **Estado:** ✅

La institucion planifica por separado la oferta tecnologica, la de grado y la de
posgrado. Un semestre calendario —`2026-1`— no es un periodo academico sino
**tres**, y el sistema los trataba como uno solo.

## El codigo institucional

```
2 6 1 65 1
│ │ │ │  └─ constante
│ │ │ └──── nivel: 15 tecnologia · 65 grado · 75 posgrado
│ │ └────── periodo del anio (1 o 2)
└─┴──────── dos ultimos digitos del anio
```

| Codigo | Nombre |
|---|---|
| `261151` | 2026-1 TECNOLOGÍA |
| `261651` | 2026-1 GRADO |
| `261751` | 2026-1 POSGRADO |

> El ejemplo del pedido daba el codigo `261151` junto al nombre «2023-1
> TECNOLOGÍA». Se siguio la regla —los dos digitos salen del anio—, asi que
> 2023-1 tecnologia es `231151` y `261151` es 2026-1.

## A que periodo va cada fila

Las reglas, en este orden:

1. **Facultad `ETECH` o `UAEFTT` → tecnologia**, sin mirar el nivel. Esas
   unidades imparten tecnologia aunque sus filas vengan etiquetadas como grado:
   78 de las 111 lo estaban.
2. Si no, manda la columna **`NIVEL`**.
3. Si `NIVEL` viene vacia, se toma del **segmento central del nombre de la
   carrera**, que tiene la forma `SEDE:NOMBRE - NIVEL - MODALIDAD`.
4. Sin ninguna de las dos, grado, que es el caso mayoritario.

### Dos cosas que las reglas del pedido no cubrian

**El pedido decia `NIVEL = GRADO` para el codigo 75.** Es una errata evidente:
75 es posgrado. Se implemento `NIVEL = POSGRADO`.

**731 filas no encajaban en ninguna de las tres reglas**: no son ETECH/UAEFTT y
tienen `NIVEL` vacia. Son **todas de 2026-1**, el periodo mas reciente. Su nivel
si esta en el nombre de la carrera —`UIO:MEDICINA VETERINARIA - GRADO -
PRESENCIAL`—, de donde se recuperan 720; las 11 restantes no tienen carrera y ya
se rechazaban antes por eso.

El respaldo mira **solo los segmentos separados por guiones**, no el texto
entero. Buscar «MAESTRIA» en cualquier parte clasificaria como posgrado las 98
carreras de grado que la mencionan en su nombre.

## El resultado

Trece periodos pasan a **treinta y uno**, no a treinta y nueve: no todos los
semestres tienen los tres niveles —la oferta tecnologica solo aparece desde
2024—.

| Periodo | Filas |
|---|---|
| 2026-1 GRADO | 1.096 |
| 2026-1 POSGRADO | 402 |
| 2026-1 TECNOLOGÍA | 25 |
| **2026-1 completo** | **1.523** |

Las 15.219 filas quedaron reasignadas, ninguna huerfana.

## El ajuste que no se veia venir

**`orden` no distingue el nivel.** Los tres periodos de un semestre comparten
`anio * 10 + periodo`.

Es deliberado y hubo que decidirlo: el reporte deriva el «anio de inicio de
actividades en la carrera» y el «anio actual» **dividiendo `orden` entre diez**.
Si el nivel entrara en esa clave, la division dejaria de dar el anio y las dos
columnas saldrian mal. Para desempatar entre los tres se ordena despues por
codigo.

**La columna `PAO` del consolidado sigue diciendo `2026-1`.** El archivo de
origen no distinguia niveles, y esa plantilla existe para contrastar contra el.
El semestre se guarda en los atributos del periodo y de ahi lo toma la
exportacion. Verificado: las 72 columnas siguen coincidiendo una a una.

## Filtrar por varios periodos

La lista del distributivo permite marcar **uno, varios o todos**. Es lo que hace
falta ahora: «ver 2026-1 entero» significa marcar sus tres periodos.

Se uso un desplegable con casillas y no un `select` multiple: los `select`
multiples se manejan con Ctrl y nadie los descubre, y con treinta y un periodos
hace falta ver que esta marcado.

Comprobado en la interfaz: tecnologia 25 + grado 1.096 = **1.121**, el numero
que muestra el contador al marcar los dos.

## Sobre el archivo

El pedido menciona `distributivo_2020_2026.xlsx`, que no existe en el
repositorio. El que cubre 2020→2026 es `docs/distributivo/distributivo.xlsx`,
15.287 filas, y es el que se analizo.

## Migracion

`1fe3adf26d90` crea los treinta y un periodos, reasigna las filas y retira los
trece antiguos. **Reversible sin perdida**: la vuelta atras rehace los
semestres originales leyendo el atributo `semestre` de cada periodo y devuelve
cada fila al suyo. Probada en los dos sentidos sobre las 15.219 filas.

Durante la prueba aparecio un fallo del camino de vuelta: el `INSERT` reutilizaba
el mismo parametro en tres columnas de tipos distintos y el driver no podia
deducir uno solo. Corregido con parametros separados.

## Pruebas

**408 en verde** (382 unitarias + 26 de integracion). Las nuevas cubren el
codigo institucional en las dos direcciones, que los tres niveles compartan
`orden` —que es lo que protege al reporte—, y las cuatro reglas de
clasificacion, incluida la que evita clasificar como posgrado una carrera de
grado que menciona «MAESTRIA».

## Lo que quedo pendiente

- **Las 11 filas sin nivel ni carrera** siguen rechazandose en la importacion,
  como antes. No es nuevo: forman parte de las 27 que ya se rechazaban.
- La clasificacion por nombre de carrera es un **respaldo**, no una regla. Si el
  origen volviera a mandar `NIVEL` en 2026-1, deja de usarse sola.
