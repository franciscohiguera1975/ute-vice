# Historico por fases

Un archivo por fase, con lo entregado, los archivos tocados y lo que quedo
pendiente.

## Convenciones

1. **Una fase cerrada no se reescribe.** Si algo cambia despues, se registra en
   la fase que lo cambio. El historico refleja lo que se creyo y decidio en cada
   momento, no una version corregida a posteriori.
2. Cada archivo indica **por que** se hizo algo, no solo que se hizo. El «que»
   se lee en el codigo; el «por que» se pierde.
3. La seccion **«Lo que quedo pendiente»** es tan importante como la de
   entregas: es donde una sesion futura encuentra el trabajo real.

## Indice

| Fase | Contenido | Estado |
|---|---|---|
| [00](00-bootstrap.md) | Bootstrap del monorepo | ✅ |
| [01](01-nucleo-backend.md) | Nucleo del backend: dominio y persistencia | ✅ |
| [02](02-auth-rbac.md) | Autenticacion y control de acceso | ✅ |
| [03](03-personas-titulos.md) | Personas, titulos e historico | ✅ |
| [04](04-consultas-senescyt.md) | Consultas al registro nacional | ✅ |
| [05](05-reportes-analitica.md) | Reportes y tablero | ✅ |
| [06](06-frontend-nucleo.md) | Frontend: nucleo y arquitectura | ✅ |
| [07](07-frontend-modulos.md) | Frontend: modulos funcionales | ✅ |
| [08](08-calidad-ci.md) | Pruebas y calidad | 🚧 |
| [09](09-distributivo.md) | Distributivo docente, catalogos y exportacion | ✅ |
| [10](10-despliegue.md) | Despliegue en VPS y entrega continua | ✅ |
| [11](11-alcance-academico.md) | Alcance academico por usuario | ✅ |
| [12](12-asignaturas-y-alcance-del-reporte.md) | Catalogo de asignaturas, seleccion multiple y personas | ✅ |
| [13](13-periodos-academicos-por-nivel.md) | Cada semestre son tres periodos academicos | ✅ |
| [14](14-sesion-expirada.md) | La sesion expirada vuelve al acceso | ✅ |
| [15](15-materias-por-docente.md) | Las materias que imparte cada docente | ✅ |
| [16](16-codigo-del-erp.md) | El codigo del ERP en los catalogos | ✅ |
| [17](17-recargar-un-periodo.md) | Recargar un periodo sin perder lo enlazado | ✅ |
| [18](18-consulta-y-cabecera.md) | Rol de consulta y cabecera institucional | ✅ |
| [19](19-bucle-de-redirecciones.md) | El bucle de redirecciones que dejaba la pantalla en blanco | ✅ |
| [20](20-nombres-en-mayusculas.md) | Nombres en mayusculas, la sede real y el nivel tecnologia | ✅ |
