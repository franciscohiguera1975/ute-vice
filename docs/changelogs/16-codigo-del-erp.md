# Fase 16 · El código del ERP en los catálogos

**Fecha:** 2026-09-14 · **Estado:** ✅

El ERP académico nombra las unidades con códigos de dos letras que no coinciden
con los del consolidado del distributivo. Traducir entre los dos mundos, cada
vez que llega un reporte del SICAF, era un conocimiento que no estaba escrito en
ninguna parte.

## El campo

`codigo_erp` se agrega a **los doce catálogos**, no solo a facultades: el SICAF
trae también `COD_CARRERA` y `COD_PERIODO`, y el día que haga falta
reconciliarlos la columna ya estará. El `MixinCatalogo` es compartido, así que
dejarla solo en facultades habría obligado a romper el modelo común.

**No es único, y no puede serlo.** Dos unidades de aquí son una sola allá:

```
FCSEE  ─┐                        ETECH  ─┐
        ├─► FS                           ├─► TT
PFCSEE ─┘                        UAEFTT ─┘
```

Por eso no lleva restricción de unicidad ni índice: la identidad sigue siendo
`codigo`, y los catálogos donde se consulta tienen decenas de filas.

## El mapeo

No se dedujo de las siglas —que en su mayoría calzan, pero cuatro no— sino de
las **carreras**: se comprobó contra los reportes del SICAF que las carreras de
cada unidad local son las que el ERP agrupa bajo ese código.

| Local | ERP | Nombre | Cómo se determinó |
|---|---|---|---|
| CEL | CL | Centro de Educación en Línea | Computación, Contabilidad, Talento Humano |
| ETECH | TT | Unidad Académica Especializada… | Desarrollo de Software, Marketing Digital |
| FAU | FU | Facultad de Arquitectura y Urbanismo | sigla |
| FCGT | FG | Facultad de Ciencias Gastronómicas y Turismo | sigla |
| FCIC | FC | Facultad de Ciencias, Ingeniería y Construcción | Ingeniería Civil |
| FCII | FI | Facultad de Ciencias de la Ingeniería e Industrias | sigla |
| FCSEE | FS | Facultad de Ciencias de la Salud Eugenio Espejo | sigla |
| FDCAS | FD | Facultad de Derecho, Ciencias Administrativas y Sociales | sigla |
| FMVA | FV | Facultad de Medicina Veterinaria y Agronomía | sigla |
| FO | FO | Facultad de Odontología | sigla |
| PEL | PL | Posgrados en Línea | 59 maestrías en línea |
| PFCSEE | FS | Posgrados de la Facultad de Ciencias de la Salud… | especializaciones médicas |
| UAEFTT | TT | Unidad Académica Especializada… | mismas carreras que ETECH |

`EC` —Educación Continua— existe en el ERP y no tiene contraparte aquí: no
imparte distributivo.

## Los nombres

Hasta ahora `nombre` repetía la sigla: `FCSEE` se llamaba «FCSEE», porque el
consolidado no traía otra cosa. Ahora llevan el nombre oficial.

**No a todas se les antepone «Facultad de».** Un centro y una unidad académica
no lo son, y llamar «Facultad de Centro de Educación en Línea» a `CEL` habría
sido peor que dejarlo como estaba. Son facultades siete de las trece; las otras
conservan su designación institucional.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/entities/catalogo.py` | campo, normalización a mayúsculas, tope de 64 |
| `infrastructure/db/modelos_distributivo.py` | columna en `MixinCatalogo` |
| `infrastructure/db/mapeadores_distributivo.py` | ida y vuelta |
| `api/esquemas/distributivo.py` | salida, alta y edición |
| `application/casos_uso/catalogos.py` | entradas de los dos casos |
| `api/v1/routers/catalogos.py` | traslado |
| `alembic/versions/…c47a1e3b8d52…` | columna en 12 tablas + mapeo + nombres |
| `frontend/…/catalogo.component.*` | campo del formulario y columna «ERP» |
| `tests/unit/test_asignaturas.py` | 5 casos |

La migración es reversible: la vuelta atrás restituye los nombres —la sigla— y
descarta la columna. Probada en los dos sentidos sobre una copia del respaldo de
producción.
