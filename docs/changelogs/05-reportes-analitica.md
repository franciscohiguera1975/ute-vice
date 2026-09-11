# Fase 05 · Reportes y tablero

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Que la informacion salga del sistema en formatos utilizables, y que el estado de
la validacion se vea de un vistazo.

## Entregado

### Exportadores

Un puerto (`ExportadorReporte`), tres implementaciones: Excel, CSV y PDF.
Agregar un formato es registrar una implementacion mas; ningun caso de uso
cambia.

Detalles que se descubren usando los archivos, no escribiendolos:

- **Excel**: numeros y fechas con su **tipo nativo**. Un numero escrito como
  texto no se puede sumar ni ordenar, y eso arruina el trabajo de quien recibe
  el archivo. Ademas: cabecera institucional, panel inmovilizado y autofiltro.
- **CSV**: separador `;` y UTF-8 **con BOM**. Excel en configuracion regional en
  espanol interpreta la coma como separador decimal —el archivo se abriria en
  una sola columna— y sin BOM lee el contenido como Latin-1, corrompiendo las
  tildes.
- **PDF**: apaisado, con anchos proporcionales y corte a 5.000 filas. Un PDF con
  decenas de miles de filas no es util para nadie; se avisa en el propio
  documento.

### Constancia de filtros

Cada reporte imprime en su cabecera los filtros aplicados, quien lo genero y
cuando. Un reporte que dice «45 personas sin titulo» no significa nada si no se
sabe si son todas o solo las de una unidad.

### Tablero

Agregaciones resueltas en la base, no en Python. La alternativa —traer las filas
y contar— seria correcta y desastrosa en cuanto el padron creciera.

Todos los indicadores viajan en **una sola respuesta**: con seis peticiones
concurrentes, los numeros podrian no ser coherentes entre si al pintarlos en la
misma pantalla.

## Decisiones

- **Puerto de analitica separado de los repositorios.** Las agregaciones son
  consultas de solo lectura sin entidades de por medio. Es una separacion CQRS
  ligera.
- **Limite de filas configurable**, con error explicito. Un reporte que agota la
  memoria del servidor es peor que uno que se niega a generarse.

## Pendiente al cerrar

- Sin constructor de reportes configurable por el usuario (Fase 10).
- Sin programacion de reportes recurrentes por correo.
- El PDF no incluye graficos.
