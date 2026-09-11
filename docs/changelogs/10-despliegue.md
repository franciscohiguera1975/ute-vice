# Fase 10 · Despliegue y entrega continua

**Fecha:** 2026-09-11 · **Estado:** ✅

La aplicacion esta publicada en <https://vice-gestion.uaeftt-ute.site>, sobre un
VPS que aloja tambien Odoo (x2), Gitea, n8n, Pensum Cloud y SEMS.

## La restriccion que definio el diseno

El servidor tiene **1,8 GB de RAM** —con ~480 MB libres— compartidos entre todas
esas aplicaciones. De ahi tres decisiones:

1. **El frontend no corre en un contenedor.** Son archivos estaticos servidos
   por el nginx del host. Un contenedor nginx mas seria memoria quitada al resto
   sin ganar nada a cambio.
2. **Angular no se compila en el VPS.** Lo compila GitHub Actions y sube el
   paquete ya construido. Compilarlo alla habria tirado de swap durante minutos.
3. **`uvicorn` arranca con 2 trabajadores**, no con los 4 de la imagen.

Quedan dos contenedores: backend y su PostgreSQL propio.

## Puertos

Todos distintos de los ya ocupados y publicados **solo en `127.0.0.1`**: al
exterior se llega unicamente por nginx.

| Servicio | Puerto |
|---|---|
| Backend | `8100` |
| PostgreSQL | `5437` |

> **El 8000 ya estaba ocupado** en el VPS por otra aplicacion. Descubrirlo antes
> de desplegar evito una colision con un servicio ajeno al proyecto.

## Entrega continua

`empujon a main → CI → (si pasa) Despliegue → VPS`

El VPS es un **destino tonto**: no clona el repositorio ni guarda credenciales de
GitHub. El flujo copia por `rsync` el codigo y el paquete compilado, ejecuta el
script de despliegue por SSH y comprueba que el sitio responde 200.

El script respalda la base antes de migrar, espera a `/health` y vuelca los
registros si no responde. Limpia imagenes huerfanas **solo de este proyecto**: un
`prune` general se llevaria lo de las otras aplicaciones del servidor.

## Tres fallos encontrados al desplegar

### El frontend de produccion apuntaba a `localhost:8000`

`angular.json` no tenia `fileReplacements` en la configuracion de produccion, asi
que el paquete compilado usaba `environment.ts` —el de desarrollo— cuyo valor por
omision es `http://localhost:8000/api/v1`. El sitio publicado habria intentado
hablar con la maquina del visitante.

Corregido: produccion usa `environment.prod.ts`, que resuelve a `/api/v1`, el
mismo origen. Verificado sobre el paquete: ya no contiene `localhost:8000`.

### PostgreSQL 18 cambio donde viven los datos

El contenedor se negaba a arrancar. La imagen 18 espera el volumen en
`/var/lib/postgresql` y coloca los datos en `18/docker`; montar en
`/var/lib/postgresql/data`, como en 16, aborta el arranque.

Estaba igual en el compose de desarrollo: **los dos quedaron corregidos**.

### La contrasena generada no cumplia la politica

El generador producia solo alfanumericos y la siembra exige un caracter
especial. Se corrigio la generacion.

## Pendiente

- **Respaldo del `.env` de produccion fuera del VPS.** Existe en un solo sitio.
- **Respaldos de la base fuera del servidor.** Hoy solo hay volcados previos a
  cada despliegue, en el mismo disco.
- Google OAuth y LDAP siguen desactivados, a falta de credenciales.
- El proveedor del SENESCYT esta en `manual` y el planificador apagado: las
  consultas al registro nacional no corren aun en produccion.
- **La contrasena de root del VPS viaja en texto plano** en el historial de la
  sesion en que se hizo este despliegue. Conviene rotarla y dejar solo acceso por
  clave.
