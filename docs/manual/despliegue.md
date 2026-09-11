# Despliegue

La aplicacion corre en <https://vice-gestion.uaeftt-ute.site>, sobre un VPS que
**aloja tambien otras aplicaciones**. Esa es la restriccion que explica casi
todas las decisiones de esta pagina.

---

## El servidor

| | |
|---|---|
| Maquina | `74.208.222.22` · Ubuntu 24.04 |
| Recursos | 1,8 GB de RAM · 10 GB de swap · 77 GB de disco |
| Raiz del proyecto | `/opt/vice-gestion` |
| Vecinos | Odoo (x2), Gitea, n8n, Pensum Cloud, SEMS, y varios mas |

**1,8 GB compartidos entre todo eso** es el dato que manda. De ahi que:

- El frontend **no** corre en un contenedor: son archivos estaticos que sirve
  el nginx del host. Un contenedor nginx mas seria memoria que se le quita al
  resto del servidor sin ganar nada.
- Angular **nunca se compila en el VPS**. Lo compila GitHub Actions y sube el
  resultado ya construido.
- `uvicorn` arranca con **2 trabajadores**, no con los 4 de la imagen.

## Puertos

Todos distintos de los que ya usaban las demas aplicaciones, y publicados
**solo en `127.0.0.1`**: al exterior se llega unicamente por nginx, que es
quien termina TLS.

| Servicio | Puerto | Expuesto |
|---|---|---|
| Backend (FastAPI) | `8100` | `127.0.0.1` |
| PostgreSQL | `5437` | `127.0.0.1` |
| Frontend | — | archivos estaticos, sin proceso |

Ocupados por otras aplicaciones y por tanto **no utilizables**: 80, 443, 3000,
3001, 3002, 5173, 5432, 5433, 5435, 5436, 5678, 5679, 8000, 8069, 8070, 2222.

> El puerto 8000 —el de desarrollo— ya estaba tomado en el VPS por otra
> aplicacion. Por eso produccion usa 8100.

## Como esta montado

```
Internet ──HTTPS──> nginx del host ─┬─ /          ─> /opt/vice-gestion/frontend  (estatico)
                                    ├─ /api/      ─> 127.0.0.1:8100  (contenedor)
                                    ├─ /health    ─> 127.0.0.1:8100
                                    └─ /docs      ─> 127.0.0.1:8100

/opt/vice-gestion/
├── .env                      secretos, permisos 600, NO se versiona
├── docker-compose.prod.yml
├── backend/                  codigo, para construir la imagen
├── frontend/                 el paquete de Angular ya compilado
├── infra/                    nginx y el script de despliegue
└── respaldos/                volcados previos a cada despliegue (7 ultimos)
```

Dos contenedores: `vice_gestion_backend` y `vice_gestion_postgres`. La base es
**propia del proyecto**, no se comparte con el PostgreSQL de Odoo que ya existia
en el servidor.

---

## Entrega continua

```
empujon a main ──> CI ──(si pasa)──> Despliegue ──> VPS
```

**CI** (`.github/workflows/ci.yml`) corre ruff, mypy y las 357 pruebas del
backend contra un PostgreSQL real, y compila el frontend.

**Despliegue** (`.github/workflows/deploy.yml`) solo arranca si CI paso.
Compila Angular, copia por `rsync` el codigo y el paquete, ejecuta el script de
despliegue por SSH y comprueba que el sitio responde 200.

El VPS es un **destino tonto**: no clona el repositorio ni guarda credenciales
de GitHub. Todo va en un sentido, de Actions hacia el servidor.

### Secretos que exige el flujo

En *Settings › Secrets and variables › Actions*:

| Secreto | Valor |
|---|---|
| `VPS_HOST` | `74.208.222.22` |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | La clave privada de despliegue, ed25519, sin passphrase |

La clave publica correspondiente ya esta en `/root/.ssh/authorized_keys` del
VPS. Es una clave **dedicada al despliegue**: no es la de nadie.

### Que hace el script en el servidor

`infra/deploy/deploy.sh`, idempotente:

1. Comprueba que existe `.env`. Si falta, aborta antes de tocar nada.
2. Construye la imagen del backend.
3. **Respalda la base** antes de migrar. Conserva los siete ultimos volcados.
4. Levanta los servicios; `alembic upgrade head` corre al arrancar el backend.
5. Espera a que `/health` responda; si no lo hace en 80 s, vuelca los registros
   y falla.
6. Siembra roles y permisos (idempotente).
7. Limpia imagenes huerfanas **solo de este proyecto**: un `prune` general se
   llevaria por delante lo que es de las otras aplicaciones del servidor.

---

## Operacion

```bash
ssh root@74.208.222.22
cd /opt/vice-gestion

docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml restart backend

# Despliegue a mano, si hiciera falta
set -a && . ./.env && set +a && bash infra/deploy/deploy.sh
```

### Consola de la base

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U ute_vice -d ute_vice
```

### Importar el consolidado de distributivo

```bash
# Desde la maquina local, subir el archivo:
rsync -az docs/distributivo/distributivo.xlsx root@74.208.222.22:/opt/vice-gestion/

# En el servidor:
docker compose -f docker-compose.prod.yml cp distributivo.xlsx backend:/tmp/
docker compose -f docker-compose.prod.yml exec backend \
  python -m app.cli importar-distributivo /tmp/distributivo.xlsx
```

### Certificado

Lo emitio certbot y **se renueva solo**; el temporizador ya estaba configurado
en el servidor para los demas dominios.

```bash
certbot certificates | grep -A2 vice-gestion
certbot renew --dry-run
```

---

## Lo que hay que saber antes de tocar nada

- **El `.env` de produccion existe solo en el servidor.** No esta en el
  repositorio ni hay copia en ninguna otra parte. Si se pierde, se pierden los
  secretos: conviene tener un respaldo fuera del VPS.
- `ENVIRONMENT=production` activa un cerrojo en la configuracion: la aplicacion
  se niega a arrancar con secretos de ejemplo, con `DEBUG=true` o con un origen
  `http://` no local en CORS. Es deliberado.
- El superusuario inicial **debe cambiar su contrasena en el primer acceso**;
  hasta que lo haga no puede navegar.
- Google OAuth y LDAP estan **desactivados** hasta que se aporten credenciales.
- El proveedor del SENESCYT esta en `manual` y el planificador apagado: las
  consultas al registro nacional no corren todavia en produccion.
