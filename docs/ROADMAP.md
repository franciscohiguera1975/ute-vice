# Roadmap — UTE-VICE

Estado de las fases. Cada fase cerrada tiene su changelog en
[`changelogs/`](changelogs/).

Leyenda: ✅ cerrada · 🚧 en curso · ⏳ planificada · 💡 idea sin confirmar

Las etapas agrupan por tema y el numero de fase dice el orden en que se hicieron
las cosas, asi que no siempre coinciden: la 09 abrio la Etapa II antes de que la
10 cerrara la Etapa I.

---

## Etapa I — Plataforma base (titulos de empleados)

### ✅ Fase 00 — Bootstrap del monorepo
Estructura del repositorio, Docker Compose (PostgreSQL 18 + backend + frontend),
variables de entorno, Makefile y esqueleto documental.
→ [changelog](changelogs/00-bootstrap.md)

### ✅ Fase 01 — Nucleo del backend
Configuracion tipada, capa de dominio (entidades, value objects, puertos,
errores), sesion asincrona de SQLAlchemy, Unit of Work, Alembic y arranque de
FastAPI con manejo centralizado de errores.
→ [changelog](changelogs/01-nucleo-backend.md)

### ✅ Fase 02 — Autenticacion y control de acceso por roles
Usuarios, roles, permisos, tokens de refresco. JWT propio (access + refresh),
inicio de sesion con Google OAuth 2.0 y proveedor LDAP/AD conectable. Guardas de
permisos en la API.
→ [changelog](changelogs/02-auth-rbac.md)

### ✅ Fase 03 — Personas, titulos e historico de consultas
Modelo y CRUD de `personas` y `titulos`, tabla `consulta_logs`, deteccion de
cambios entre consultas, busqueda y paginacion.
→ [changelog](changelogs/03-personas-titulos.md)

### ✅ Fase 04 — Consultas al SENESCYT
Puerto `TitleLookupProvider` con tres implementaciones (mock, manual
human-in-the-loop, oficial por convenio). Jobs de cobertura reanudables,
planificador con jitter y perfil horario, reconciliador de titulos.
→ [changelog](changelogs/04-consultas-senescyt.md)

### ✅ Fase 05 — Reportes y analitica
Exportacion a Excel, CSV y PDF sobre un puerto `ReportExporter`. Consultas
agregadas para el dashboard (cobertura, distribucion por nivel, tendencia).
→ [changelog](changelogs/05-reportes-analitica.md)

### ✅ Fase 06 — Frontend Angular: nucleo
Workspace Angular 20 standalone, arquitectura limpia por capas
(domain / data / features / shared), interceptores, guardas por permiso, store de
sesion con signals, layout y pantalla de acceso.
→ [changelog](changelogs/06-frontend-nucleo.md)

### ✅ Fase 07 — Frontend Angular: modulos funcionales
Dashboard con graficos, CRUD de personas y titulos, consola de consultas
SENESCYT (incluida la resolucion manual de captcha), historico de logs,
administracion de usuarios y roles, y generacion de reportes.
→ [changelog](changelogs/07-frontend-modulos.md)

### 🚧 Fase 08 — Calidad, pruebas e integracion continua
Pruebas unitarias de dominio y casos de uso, pruebas de integracion de la API,
pruebas de componentes en Angular, pipeline de CI y endurecimiento.
→ [changelog](changelogs/08-calidad-ci.md)

### ✅ Fase 10 — Despliegue y entrega continua
Publicada en <https://vice-gestion.uaeftt-ute.site> sobre un VPS compartido con
otras seis aplicaciones. Dos contenedores —backend y su PostgreSQL— en puertos
propios y solo accesibles por `127.0.0.1`; el frontend son archivos estaticos que
sirve el nginx del host.

La entrega continua va en un solo sentido: GitHub Actions prueba, compila y
empuja al servidor. El VPS no clona el repositorio ni guarda credenciales.

→ [changelog](changelogs/10-despliegue.md) · [manual](manual/despliegue.md)

---

## Etapa II — Expansion del modelo de datos

### ✅ Fase 09 — Distributivo docente y catalogos
Tabla `distributivo` con los doce catalogos que alimentan sus selectores, CRUD
de todos, importacion del consolidado historico (15.219 filas, 2020-1 → 2026-1)
y exportacion con **plantillas intercambiables**: la institucional y la que
reproduce el archivo de origen para contrastar.

La estructura de plantillas es el aporte que sobrevive a esta fase: agregar un
formato es escribir una clase en `app/application/plantillas/` y registrarla. Ni
el caso de uso, ni el router, ni el frontend cambian, porque la interfaz
pregunta que plantillas hay en lugar de tenerlas fijas.

→ [changelog](changelogs/09-distributivo.md) · [manual](manual/distributivo.md)

### ✅ Fase 11 — Alcance academico por usuario
Cada cuenta se acota a un conjunto de facultades y carreras. Vacio no restringe
nada, que es lo que permitio desplegarlo sin dejar a nadie sin ver. El recorte
lo impone el servidor a partir del actor, nunca la peticion.

→ [changelog](changelogs/11-alcance-academico.md) · [manual](manual/usuarios-y-roles.md)

### ⏳ Fase 12 — Tablas adicionales
> **Pendiente de confirmacion funcional del Vicerrectorado.**

Tablas candidatas identificadas pero no confirmadas:
- Unidades academicas / dependencias (hoy es texto libre en `personas`).
- Cargos y escalafon docente.
- Contratos y periodos de vinculacion.
- Capacitaciones y certificaciones no titulantes.
- Produccion academica (publicaciones, proyectos).

**Como se agrega una tabla nueva sin romper nada:** el procedimiento esta escrito
en [`manual/extender-modelo.md`](manual/extender-modelo.md). La arquitectura ya
esta preparada: cada tabla nueva es una entidad de dominio, un puerto de
repositorio, una implementacion SQLAlchemy, un conjunto de casos de uso y un
router — sin tocar lo existente (principio abierto/cerrado).

### ⏳ Fase 13 — Motor generico de reportes
Constructor de reportes configurable por el usuario (elegir tabla, columnas,
filtros y formato) sobre el puerto `ReportExporter` ya existente. El registro de
plantillas de la Fase 09 es el paso previo: ya separa «que columnas salen» de
«como se genera el archivo».

---

## Etapa III — Capa inteligente

Toda esta etapa se apoya en una decision tomada desde la Fase 01: los casos de uso
son objetos con una firma unica (`execute(input) -> output`) y no dependen de
FastAPI. Eso permite exponerlos como herramientas de un agente sin reescribirlos.
Ver [ADR-0006](adr/0006-preparacion-capa-ia.md).

### ⏳ Fase 14 — Registro de skills
Catalogo de capacidades invocables (`ports/skill.py`) donde cada caso de uso se
publica con su esquema JSON de entrada/salida y el permiso que exige.

### ⏳ Fase 15 — Servidor MCP
Exponer el registro de skills como servidor MCP para que cualquier cliente
compatible (Claude, IDEs) opere sobre los datos respetando el RBAC del usuario.

### ⏳ Fase 16 — Consultas en lenguaje natural
Traduccion de preguntas a invocaciones de skills. **Restriccion de diseno:** el
modelo no genera SQL libre; solo puede componer skills registradas, que ya llevan
sus filtros de permisos. Esto evita fuga de datos y SQL injection semantica.

### ⏳ Fase 17 — Agentes de tarea
Agentes que encadenan skills: "revisa que personas no tienen titulo registrado y
genera el reporte para Talento Humano".

### 💡 Fase 18 — Interfaz de voz ("Jarvis")
Reconocimiento de voz (entrada) y sintesis (salida) sobre la capa de agentes.
Pendiente de definir: procesamiento local vs. servicio externo — decision
condicionada por tratarse de datos personales (ver [SECURITY.md](SECURITY.md)).

---

## Fuera de alcance (decision explicita)

Estas capacidades fueron solicitadas y **no se implementan**, por tratarse de
evasion de controles antibot:

- Resolucion automatizada de captchas del portal del SENESCYT.
- Rotacion de proxies o VPN orientada a no ser detectado como automatizacion.
- Cualquier tecnica cuyo proposito sea no activar alarmas de abuso del proveedor.

La alternativa implementada — cola manual asistida, presupuesto conservador de
peticiones y via formal de convenio — esta descrita en [SENESCYT.md](SENESCYT.md).
