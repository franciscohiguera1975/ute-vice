# Fase 07 · Frontend: modulos funcionales

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Todas las pantallas funcionales, verificadas contra el backend real.

## Entregado

### Tablero

Indicadores, alertas accionables y cuatro graficos en **SVG generado a mano**.

Se evito una libreria de graficos deliberadamente: estos tipos son simples, y
una dependencia externa costaria cientos de kilobytes, un tema propio que no
encaja con el resto, y una superficie de actualizacion mas. Los graficos toman
su paleta de las variables CSS, asi que siguen el tema claro u oscuro sin codigo
adicional.

Las alertas enlazan al listado ya filtrado: «31 personas nunca consultadas» va a
`/personas?nuncaConsultadas=true`.

### Personas

Listado con busqueda difusa retrasada, filtros, ordenamiento y paginacion.
Detalle con expediente academico, separando **titulos vigentes** de **retirados**
—estos ultimos con su explicacion, porque son el hallazgo a auditar—.

Formulario con validacion de cedula en el navegador: el algoritmo de modulo 10
duplicado a proposito para dar respuesta inmediata sin viaje al servidor. El
backend sigue siendo la autoridad.

Al consultar una persona ya cubierta en el periodo, la respuesta 409 no deja al
usuario sin salida: se ofrece forzar, explicando el costo.

### Consultas

Tres vistas: campanas, historico y planificador.

- **Campanas**: progreso, contadores, cortacircuitos con su explicacion, y
  avance manual paso a paso —que sirve tanto para operar sin planificador
  automatico como para diagnosticar, porque la respuesta dice por que se
  consulto o por que no—.
- **Historico**: la bitacora, con detalle de cambios campo a campo mostrando
  valor anterior y nuevo. Desde aqui se **resuelven los desafios de
  verificacion**.
- **Planificador**: existe sobre todo para responder «¿por que el sistema no
  esta consultando ahora mismo?». Muestra la franja vigente, el presupuesto y la
  capacidad estimada, en lugar de dejar que el comportamiento parezca
  arbitrario.

### Reportes, administracion y perfil

Generador con filtros por tipo y formato; matriz de roles y permisos agrupada
por modulo, con el catalogo servido desde el backend para que no exista una
copia desincronizada; gestion de usuarios con las protecciones del backend
reflejadas en la interfaz.

## Ampliacion del backend

Se expuso `desafio_id` en el esquema de `ConsultaLogSalida`, solo para los
registros en estado `DESAFIO_PENDIENTE`. Sin ese dato, el operador no tenia como
resolver un desafio desde donde lo ve.

## Verificacion

La aplicacion se levanto contra PostgreSQL y el backend reales, y se recorrio en
el navegador: acceso, cambio de contrasena obligatorio, tablero con datos,
creacion y avance de una campana, listado y detalle de personas, reportes,
matriz de permisos y planificador.

De ahi salieron los dos fallos registrados en la Fase 06 y la clasificacion
incorrecta de nivel registrada en la Fase 04.

## Pendiente al cerrar

- Sin importacion de personas desde archivo en la interfaz: el endpoint existe,
  falta el selector y la previsualizacion.
- Sin edicion de titulos manuales desde la interfaz.
- El PDF de reportes no incluye graficos.
