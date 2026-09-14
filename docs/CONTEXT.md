# Contexto del proyecto — punto de retomada

> **Este documento es el traspaso entre sesiones de trabajo.** Si eres una IA
> que retoma este proyecto sin haber participado antes, lee esto completo antes
> de tocar nada. Se actualiza al cerrar cada fase.

**Ultima actualizacion:** 2026-09-11
**Fases cerradas:** 00 → 07, 09 → 13 · **En curso:** 08 (calidad y pruebas)
**Estado:** **en produccion** en <https://vice-gestion.uaeftt-ute.site>

---

## 1. Que es este sistema

**UTE Vice — Gestion Academica.** Plataforma para el Vicerrectorado de la UTE.
Empezo centralizando los **titulos universitarios del personal** y validandolos
contra el registro nacional (SENESCYT); desde la Fase 09 cubre tambien el
**distributivo docente**.

Entregado y funcionando:

- CRUD de personas (padron del personal) y de sus titulos academicos.
- Consulta automatizada al registro nacional por cedula, con historico completo
  de cada intento.
- Deteccion de cambios entre consultas: titulos nuevos, modificados y retirados.
- Distributivo docente con sus doce catalogos, captura de la asignatura que
  imparte y exportacion con plantillas intercambiables.
- Tablero de indicadores y reportes en Excel, CSV y PDF.
- Autenticacion local, Google OAuth y directorio activo, con control de acceso
  por permisos.

## 2. Estado verificado

| Componente | Estado |
|---|---|
| Backend | **408 pruebas en verde** (382 unitarias + 26 de integracion) |
| Base de datos | 27 tablas; migracion aplica y revierte sobre PostgreSQL 18 real |
| Frontend | Compila sin avisos; 343 kB iniciales (100 kB comprimidos) |
| Verificacion | Recorrido completo en navegador contra backend y base reales |

Ese recorrido incluyo: acceso, cambio obligatorio de contrasena, tablero con
datos, creacion y avance de una campana, listado y detalle de personas, reportes
y matriz de permisos. En la Fase 09 se sumaron: exportacion del distributivo en
las dos plantillas y captura de asignaturas guardada de extremo a extremo, con
**15.219 filas reales** importadas del consolidado.

## 3. Decisiones que NO deben revertirse sin discusion

| # | Decision | Por que | ADR |
|---|---|---|---|
| 1 | El dominio no importa nada de infraestructura | Sostiene toda la arquitectura. Hay una prueba que lo verifica | [0001](adr/0001-arquitectura-limpia.md) |
| 2 | La autorizacion se resuelve por **permiso**, nunca por rol | Agregar un rol no obliga a tocar codigo | [0002](adr/0002-autorizacion-por-permiso.md) |
| 3 | Los casos de uso tienen firma unica `(entrada, contexto) → salida` | Permite publicarlos como skills en la Fase 11 sin reescribirlos | [0006](adr/0006-preparacion-capa-ia.md) |
| 4 | **No se automatiza la resolucion de captchas** | Ver seccion 5 | [0005](adr/0005-consultas-senescyt.md) |
| 5 | Los titulos nunca se borran; se marcan `RETIRADO` | Un titulo que desaparece del registro es el hallazgo a auditar | [0004](adr/0004-identidad-de-titulos-por-huella.md) |
| 6 | Se escribe en `consulta_logs` en **todos** los casos | Sin ello, un dato desfasado es indistinguible de uno no consultado | — |
| 7 | Un solo job de cobertura activo a la vez | Dos campanas romperian la garantia de no repetir personas | — |
| 8 | La politica de ritmo vive en el dominio | Hace verificable el comportamiento horario sin esperar horas | [0007](adr/0007-ritmo-en-el-dominio.md) |

## 4. Estructura

```
ute-vice/
├── docker-compose.yml     postgres 18 + backend + frontend
├── Makefile               make up · make seed · make test
├── .env.example           plantilla documentada
├── backend/src/app/
│   ├── core/              configuracion tipada, registro estructurado
│   ├── domain/            entidades, value objects, puertos, servicios
│   ├── application/       casos de uso
│   ├── infrastructure/    PostgreSQL, JWT, SENESCYT, exportadores
│   └── api/               routers, esquemas, dependencias
├── frontend/src/app/
│   ├── domain/            modelos y puertos (espejo del backend)
│   ├── data/              implementaciones HTTP
│   ├── core/              sesion, interceptores, guardas
│   ├── shared/            componentes, directivas, layout
│   └── features/          pantallas, con carga diferida
└── docs/                  esta carpeta
```

## 5. El asunto del captcha — leer antes de tocar el modulo de consultas

El portal publico del SENESCYT protege sus consultas con captcha. Durante el
diseno se solicito automatizar su resolucion, rotar proxies y espaciar las
peticiones para no activar alarmas de deteccion.

**Eso no se implemento, y es una decision deliberada.** Automatizar un captcha o
enmascarar el origen de las peticiones es evadir un control de acceso, con
independencia de que el fin —validar titulos del propio personal— sea legitimo.

Lo que si se construyo:

| Requisito original | Solucion entregada |
|---|---|
| Peticiones espaciadas, no simultaneas | Jitter aleatorio + presupuesto por hora |
| Mas consultas 08–17, menos 17–21 | Perfil horario con pesos (`PoliticaPlanificacion`) |
| Campana de varios dias que sepa donde quedo | `JobCobertura` + `ItemJob`, reanudables |
| No repetir persona hasta cubrir a todas | `PeriodoCobertura` + `Persona.requiere_consulta()` |
| Resolver captcha | Cola *human-in-the-loop*: un operador lo transcribe |
| Proxies / VPN | No implementado. La via correcta es el convenio institucional |

`ProveedorConsultaTitulos` tiene tres implementaciones (`mock`, `manual`,
`oficial`). Si la UTE consigue el convenio, se cambia una variable de entorno y
no se toca dominio ni casos de uso.

Contexto completo en [`SENESCYT.md`](SENESCYT.md).

## 6. Como levantarlo

```bash
cp .env.example .env    # ajustar SECRET_KEY y contrasenas
make up
make seed               # roles, permisos y superusuario
make seed-demo          # opcional: 60 personas ficticias
```

- Interfaz: <http://localhost:4200>
- API: <http://localhost:8000/docs>

El superusuario debe cambiar su contrasena en el primer acceso; hasta entonces
no puede navegar.

## 7. Donde continuar

### Fase 08 — en curso

Lo pendiente esta en [`changelogs/08-calidad-ci.md`](changelogs/08-calidad-ci.md):

- Pruebas de componentes en Angular (la arquitectura las hace faciles; no se han
  escrito).
- Pipeline de integracion continua.
- Umbral de cobertura.

### Trabajo funcional identificado

- Importacion de personas desde archivo **en la interfaz** (el endpoint existe).
- Edicion de titulos manuales desde la interfaz.
- Implementar `_analizar_html()` del proveedor `manual` contra el portal real.
- Notificaciones cuando el cortacircuitos pausa una campana.
- Bitacora de operaciones administrativas (el permiso `auditoria:leer` esta
  reservado).

### Fase 09 — cerrada

Distributivo docente, sus doce catalogos y la exportacion con plantillas. Lo
entregado y lo pendiente, en
[`changelogs/09-distributivo.md`](changelogs/09-distributivo.md); el uso, en
[`manual/distributivo.md`](manual/distributivo.md).

Lo que quedo abierto ahi:

- Reimportacion incremental de un periodo sin tocar los demas.
- Mas plantillas de exportacion. La estructura esta para eso: se escribe una
  clase en `app/application/plantillas/`, se registra, y aparece sola en el
  selector del frontend.
- `SEDE` sale normalizada en la plantilla de origen; si hiciera falta el texto
  literal del consolidado, habria que guardarlo al importar.

### Fase 10 — cerrada

Desplegada en el VPS con entrega continua desde GitHub Actions. El detalle —los
puertos, la restriccion de memoria que definio el diseno y los tres fallos que
aparecieron al desplegar— en
[`changelogs/10-despliegue.md`](changelogs/10-despliegue.md); la operacion, en
[`manual/despliegue.md`](manual/despliegue.md).

Lo que quedo abierto:

- **El `.env` de produccion existe en un solo sitio**, el servidor. Sin copia
  fuera, perderlo es perder los secretos.
- **Los respaldos de la base viven en el mismo disco** que la base.
- La contrasena de root del VPS viajo en texto plano en la sesion del
  despliegue: conviene rotarla y dejar solo acceso por clave.

### Fase 11 — cerrada

Alcance academico: cada cuenta se acota a un conjunto de facultades y carreras.
Detalle en [`changelogs/11-alcance-academico.md`](changelogs/11-alcance-academico.md);
el uso, en [`manual/usuarios-y-roles.md`](manual/usuarios-y-roles.md).

Lo que quedo abierto: `personas` y `titulos` no se acotan —su `unidad` es texto
libre y habria que normalizarla antes—, y no hay alcance por sede.

### Fases 12 a 16 — cerradas

**12**: asignatura pasa a catalogo con varias materias por fila; la exportacion
admite varios periodos, facultades y carreras; las personas se crean desde el
padron docente ([changelog](changelogs/12-asignaturas-y-alcance-del-reporte.md)).

**13**: cada semestre son tres periodos academicos —tecnologia, grado y
posgrado—, con codigo institucional de seis digitos
([changelog](changelogs/13-periodos-academicos-por-nivel.md)).

> Al tocar los periodos, recuerde que **`orden` no distingue el nivel** a
> proposito: el reporte deriva el anio dividiendolo entre diez, y los tres
> periodos de un semestre deben seguir dando el mismo anio.

**14**: al caducar el token la aplicacion vuelve al acceso con un solo aviso, y
la renovacion automatica de sesion funciona por primera vez
([changelog](changelogs/14-sesion-expirada.md)). Trae ademas las **primeras
pruebas del frontend**; el orden de los interceptores vive en `INTERCEPTORES`
—no en `app.config.ts`— porque es parte de su comportamiento y alli las pruebas
lo cubren.

**15**: las materias que imparte cada docente se cargan desde el reporte del
SICAF ([changelog](changelogs/15-materias-por-docente.md)).

> El origen agrupa por **docente y semestre**; el distributivo, por docente,
> periodo, carrera y sede. Las materias se enlazan a **todas** las filas del
> docente en ese semestre: el archivo no dice a que carrera pertenece cada una,
> y repartirlas seria inventar la atribucion.
>
> Ojo con el **codigo de tecnologia**: el SICAF usa `55` y el sistema `15`.
> **Se decidio conservar el `15`** —es el de los periodos ya emitidos y los
> informes que ya circularon—, asi que la traduccion ocurre al importar, en
> `_NIVELES`. No es una errata: no lo «corrija».

**16**: los catalogos guardan `codigo_erp`, el nombre del mismo elemento en el
ERP academico ([changelog](changelogs/16-codigo-del-erp.md)).

> **No es unico**: `FCSEE` y `PFCSEE` son dos unidades aqui y una sola —`FS`—
> alla, igual que `ETECH` y `UAEFTT` son ambas `TT`. La identidad sigue siendo
> `codigo`; `codigo_erp` solo reconcilia.

### Fase 14 — espera confirmacion funcional

El Vicerrectorado no ha confirmado que tablas adicionales incorporar. El
procedimiento para agregar una sin romper nada esta en
[`manual/extender-modelo.md`](manual/extender-modelo.md).

## 8. Fallos ya encontrados y corregidos

No los reintroduzcas. Estan documentados en el changelog de su fase:

1. Mitigacion de temporizacion inefectiva en el inicio de sesion (Fase 02)
2. `seed` fallando con la contrasena de ejemplo (Fase 02)
3. Fallo de borde en la regla de cobertura del periodo (Fase 03)
4. Reparto de items duplicando el control de ritmo (Fase 04)
5. Clasificacion incorrecta del nivel academico (Fase 04)
6. `inject()` fuera de contexto en el interceptor HTTP (Fase 06)
7. `LOCALE_ID` sin datos de configuracion regional (Fase 06)
8. `CORS_ORIGINS` abortando el arranque con el formato documentado (Fase 08)
9. La bateria de pruebas pasaba por accidente del orden: el fixture de esquema
   no importaba los modelos, y `create_all` no creaba nada (Fase 08)
10. Una prueba de integracion que solo pasaba en horario de oficina, porque
    dependia del reloj real (Fase 08)
11. Clave natural incompleta en el distributivo: sin la sede, un docente que
    dicta la misma carrera en dos campus colisionaba consigo mismo (Fase 09)
12. `UNIQUE` sin `NULLS NOT DISTINCT`: la restriccion tenia un agujero justo en
    las filas sin sede, que es donde mas falta hacia (Fase 09)
13. Dos plantillas contando «sin asignatura» con reglas distintas, y ninguna
    coincidiendo con el filtro de la pantalla de captura (Fase 09)
14. El exportador PDF sin suelo de ancho de columna: con 72 columnas devolvia
    un 500 en lugar de decir que no caben (Fase 09)
15. Las pruebas de integracion apuntando por omision a `ute_vice` en lugar de
    `ute_vice_test`: correr la bateria borraba la base de desarrollo (Fase 09)
16. El paquete de produccion de Angular apuntando a `localhost:8000`, porque
    `angular.json` no reemplazaba el archivo de entorno (Fase 10)
17. El volumen de PostgreSQL 18 montado en `/var/lib/postgresql/data`, como en
    la 16: el contenedor se niega a arrancar (Fase 10)
18. La bateria de pruebas solo coleccionaba con `python -m pytest`, que agrega
    el directorio actual a la ruta. Con `pytest` a secas —como la llaman el
    Makefile y CI— fallaban cinco modulos (Fase 10)
19. La fila resuelta no cargaba los identificadores de sus asignaturas:
    `requiere_asignatura` mentia y guardar la entidad borraba los enlaces
    (Fase 12)
20. Los arreglos en parametros de consulta viajaban como `"a,b"` en lugar de
    repetir el parametro, que es lo que espera FastAPI (Fase 12)
21. Un `INSERT` de migracion reutilizando el mismo parametro en columnas de
    tipos distintos: el driver no puede deducir uno solo (Fase 13)
22. Los interceptores HTTP registrados al reves: el de autenticacion recibia el
    error ya normalizado, no reconocia el 401, y ni la renovacion de sesion ni
    el redirigir al acceso se ejecutaron nunca (Fase 14)

El octavo es el mas ilustrativo: un fallo en la ruta feliz de la configuracion
de ejemplo, que solo aparecio al arrancar con un `.env` realista. El noveno, el
decimo y el 18 son del mismo tipo: pruebas que pasaban por una razon distinta
de la que se creia.

El 22 es el unico que no producia sintoma alguno donde estaba el error —ni
excepcion, ni aviso en consola, ni prueba en rojo—, solo pantallas vacias tres
capas mas arriba. Codigo correcto, cableado al reves. Cuando algo «no hace
nada», sospeche del cableado antes que de la logica.

## 9. Antes de dar algo por terminado

- `make test` en verde (350 unitarias) y `make test-integracion` tambien (26).
  Son dos objetivos: las de integracion recrean el esquema y se niegan a correr
  contra una base que no termine en `_test`.
- `make lint` sin errores.
- El frontend compila sin avisos y sus pruebas pasan: `npm run test:ci` desde
  `frontend/`, con `CHROME_BIN` apuntando a un Chrome instalado.
- **Levantar la aplicacion y abrirla.** Tres de los ocho fallos de la lista
  anterior no los habria encontrado ninguna prueba unitaria.
- Registrar la fase en `docs/changelogs/` y actualizar este documento.
