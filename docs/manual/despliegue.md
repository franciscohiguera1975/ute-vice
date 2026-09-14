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

### Puesta en marcha, paso a paso

Hay que hacerlo **una sola vez**. Despues, cada empujon a `main` despliega solo.

#### 1. Crear una clave dedicada al despliegue

Una clave propia, con **nombre distinto** del de las que ya existen en el
servidor. El servidor aloja varias aplicaciones y varias personas: si el
despliegue reutilizara una clave personal, revocarla por cualquier motivo
—alguien deja el equipo, se cambia de portatil— dejaria de desplegar sin que
nadie relacione una cosa con la otra.

Desde la maquina local:

```bash
ssh-keygen -t ed25519 -N "" \
  -C "github-actions-despliegue-vice-gestion" \
  -f ~/.ssh/id_ed25519_vice_despliegue
```

- `-N ""` la deja **sin passphrase**. Es obligatorio: GitHub Actions no puede
  escribir una contrasena cuando se le pida.
- `-C` es solo un comentario, pero es el que aparece en `authorized_keys` del
  servidor. Con nueve claves autorizadas, es lo unico que permite saber cual es
  cual dentro de seis meses.
- `-f` fija el nombre. **No use el nombre por omision** (`id_ed25519`): eso
  sobrescribiria su clave personal sin preguntar.

Quedan dos archivos:

| Archivo | Que es | Donde va |
|---|---|---|
| `id_ed25519_vice_despliegue` | La clave **privada** | Secreto de GitHub |
| `id_ed25519_vice_despliegue.pub` | La clave **publica** | El servidor |

#### 2. Autorizar la clave publica en el servidor

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_vice_despliegue.pub root@74.208.222.22
```

Si `ssh-copy-id` no esta disponible:

```bash
cat ~/.ssh/id_ed25519_vice_despliegue.pub | \
  ssh root@74.208.222.22 'cat >> /root/.ssh/authorized_keys'
```

Comprobar que entra **sin pedir contrasena**:

```bash
ssh -i ~/.ssh/id_ed25519_vice_despliegue -o BatchMode=yes \
  root@74.208.222.22 'echo funciona'
```

`BatchMode=yes` hace que falle en lugar de pedir contrasena, que es justo lo que
interesa comprobar: asi se comportara GitHub Actions.

#### 3. Cargar los secretos en GitHub

En el repositorio: **Settings › Secrets and variables › Actions › New
repository secret**. Tres, uno por uno:

| Secreto | Valor | De donde sale |
|---|---|---|
| `VPS_HOST` | `74.208.222.22` | — |
| `VPS_USER` | `root` | — |
| `VPS_SSH_KEY` | El contenido **completo** de la clave privada | `cat ~/.ssh/id_ed25519_vice_despliegue` |

Para copiar la privada al portapapeles sin verla pasar por pantalla:

```bash
# Linux (X11)
xclip -sel clip < ~/.ssh/id_ed25519_vice_despliegue
# Wayland
wl-copy < ~/.ssh/id_ed25519_vice_despliegue
```

Sobre `VPS_SSH_KEY`, tres cosas que suelen fallar:

- Va **entera**, incluidas las lineas `-----BEGIN OPENSSH PRIVATE KEY-----` y
  `-----END OPENSSH PRIVATE KEY-----`.
- Con el **salto de linea final**. Sin el, `ssh` responde
  `error in libcrypto` y el despliegue falla sin mas explicacion.
- Es la **privada**, no la `.pub`. Es el error mas comun, y el mensaje que da
  no lo sugiere.

#### 4. Crear el entorno `produccion` (opcional pero recomendable)

En **Settings › Environments › New environment**, con el nombre `produccion`.
El flujo ya lo declara, asi que funciona sin crearlo; crearlo permite ademas
exigir una aprobacion manual antes de publicar: *Required reviewers*.

#### 5. Probar

**Actions › Despliegue › Run workflow**. No hace falta empujar nada: el flujo
admite ejecucion manual. Si termina en verde, ya esta.

> **Si falta alguno, el flujo lo dice.** Antes de intentar conectarse comprueba
> los tres y, si alguno esta vacio, termina con un mensaje que los nombra. Sin
> esa comprobacion el fallo aparecia como un `ssh-keyscan` sin explicacion, con
> el registro mostrando `MAQUINA:` en blanco.

### Que hacer si el despliegue falla

| Sintoma | Causa casi siempre |
|---|---|
| `Permission denied (publickey)` | La publica no quedo en `authorized_keys`, o en `VPS_SSH_KEY` se pego la `.pub` |
| `error in libcrypto` | A la clave privada le falta el salto de linea final |
| `Host key verification failed` | Cambio la huella del servidor; el flujo la reconoce solo con `ssh-keyscan`, revise que `VPS_HOST` sea correcto |
| `FALTA /opt/vice-gestion/.env` | El archivo se borro en el servidor. No esta en el repositorio: hay que rehacerlo |

### Rotar la clave de despliegue

Se hace sin interrumpir nada: primero se agrega la nueva y se prueba, y solo
despues se quita la vieja.

```bash
# 1. Crear la nueva y autorizarla
ssh-keygen -t ed25519 -N "" -C "despliegue-vice-gestion-2027" \
  -f ~/.ssh/id_ed25519_vice_despliegue_2027
ssh-copy-id -i ~/.ssh/id_ed25519_vice_despliegue_2027.pub root@74.208.222.22

# 2. Reemplazar el secreto VPS_SSH_KEY en GitHub y lanzar el flujo a mano

# 3. Con el despliegue en verde, retirar la anterior del servidor
ssh root@74.208.222.22 \
  "sed -i '/github-actions-despliegue-vice-gestion/d' /root/.ssh/authorized_keys"
```

El `sed` busca por el comentario de la clave: de ahi que convenga ponerle uno
descriptivo al crearla.

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

## Entrar a la aplicacion

### Donde estan las credenciales

En **`/opt/vice-gestion/.env`, en el servidor**. No estan en el repositorio: ahi
solo vive la plantilla [`.env.prod.example`](../../.env.prod.example), con los
campos vacios.

```bash
ssh root@74.208.222.22 'grep -E "^FIRST_SUPERUSER_(EMAIL|PASSWORD)=" /opt/vice-gestion/.env'
```

Se generaron con `openssl rand` al desplegar. **No hay copia en ninguna otra
parte**: si se pierde ese archivo, se pierden.

### El primer acceso

1. Abrir <https://vice-gestion.uaeftt-ute.site>.
2. Entrar con el correo y la contrasena que devolvio el comando anterior.
3. El sistema **exige cambiar la contrasena** antes de dejar navegar. Es
   deliberado: la inicial la genero un script y quedo escrita en un archivo del
   servidor.

### Crear cuentas para otras personas

Desde la interfaz, en *Administración › Usuarios › Nuevo usuario*. La contrasena
que se fije ahi es provisional: el sistema obliga a cambiarla en el primer
acceso, para que la que conocio quien creo la cuenta deje de servir.

La politica exige **minimo 10 caracteres con mayuscula, minuscula, digito y un
caracter especial**, y rechaza secuencias obvias (`123456`, `qwerty`, `admin`,
`ute2026`…). Conviene tenerlo presente al pensar un patron de claves iniciales:
uno que parezca razonable —el usuario mas unos digitos— se rechaza si no lleva
mayuscula.

Para crear varias de una vez, o sin obligar al cambio de clave, se puede hacer
desde el contenedor con el modelo de dominio. Para levantar la obligacion de
cambiarla en una cuenta ya creada:

```bash
cd /opt/vice-gestion
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U ute_vice -d ute_vice -c \
  "UPDATE usuarios SET debe_cambiar_contrasena = false WHERE email = 'alguien@ute.edu.ec';"
```

### Si se pierde la contrasena

La del `.env` solo sirve para el alta inicial: una vez cambiada, ese valor ya no
abre nada. Para recuperar el acceso:

```bash
cd /opt/vice-gestion
docker compose -f docker-compose.prod.yml exec backend \
  python -m app.cli reset-password --email admin@ute.edu.ec
```

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
