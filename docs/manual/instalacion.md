# Instalacion y puesta en marcha

## Requisitos

- Docker 24+ con Compose v2
- 4 GB de RAM disponibles
- Puertos libres: 8000 (API), 4200 (interfaz), 5433 (PostgreSQL)

Para desarrollar sin contenedores: Python 3.12+ y Node 20+.

---

## Arranque rapido

```bash
git clone <repositorio> ute-vice
cd ute-vice

cp .env.example .env
# Editar .env: al menos SECRET_KEY y las contrasenas

make up      # levanta postgres, backend y frontend
make seed    # crea permisos, roles y el superusuario
```

- Interfaz: <http://localhost:4200>
- API: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/health>

Ingrese con el correo y la contrasena de `FIRST_SUPERUSER_*`. **El sistema
obligara a cambiarla en el primer acceso**, y hasta hacerlo no dejara navegar:
esa contrasena la conoce quien preparo el despliegue.

### Datos de prueba

```bash
make seed-demo    # 60 personas ficticias
```

Despues, cree una campana desde *Consultas → Campanas* para poblar los titulos.
Con `SENESCYT_PROVIDER=mock` los datos son ficticios pero deterministas.

---

## Configuracion

Todo se controla desde `.env`. Los bloques que hay que revisar antes de usar el
sistema en serio:

### Secreto y contrasenas

```bash
# Generar un secreto real:
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

```bash
SECRET_KEY=<el generado>
POSTGRES_PASSWORD=<contrasena fuerte>
FIRST_SUPERUSER_EMAIL=admin@ute.edu.ec
FIRST_SUPERUSER_PASSWORD=<contrasena fuerte>
```

La contrasena del superusuario debe cumplir la politica: 10 caracteres o mas,
con mayuscula, minuscula, digito y caracter especial, sin secuencias comunes.

### Proveedor de consultas

```bash
SENESCYT_PROVIDER=mock     # mock | manual | oficial
```

Ver [consultas-senescyt.md](consultas-senescyt.md).

### Ritmo de consultas

```bash
SCHEDULER_ENABLED=false              # el planificador automatico llega apagado
SCHEDULER_PERIOD_DAYS=90             # ventana de cobertura
SCHEDULER_MAX_REQUESTS_PER_HOUR=30   # tope duro
SCHEDULER_PEAK_START_HOUR=8          # franja de mayor actividad
SCHEDULER_PEAK_END_HOUR=17
SCHEDULER_OFFPEAK_END_HOUR=21        # fuera de aqui no se consulta
```

Con estos valores la capacidad es de unas 262 consultas por dia. Puede
verificarlo:

```bash
docker compose exec backend python -m app.cli info
```

### Acceso con Google

```bash
GOOGLE_OAUTH_ENABLED=true
GOOGLE_CLIENT_ID=<de la consola de Google Cloud>
GOOGLE_CLIENT_SECRET=<idem>
GOOGLE_REDIRECT_URI=https://vice.ute.edu.ec/api/v1/auth/google/callback
GOOGLE_ALLOWED_DOMAINS=ute.edu.ec
```

En Google Cloud: crear credenciales OAuth 2.0 de tipo «aplicacion web» y
registrar exactamente la misma URI de redireccion.

### Acceso con directorio activo

```bash
LDAP_ENABLED=true
LDAP_SERVER_URI=ldaps://ad.ute.edu.ec:636
LDAP_USE_SSL=true
LDAP_BIND_DN=CN=svc_ute_vice,OU=Servicios,DC=ute,DC=edu,DC=ec
LDAP_BIND_PASSWORD=<contrasena de la cuenta de servicio>
LDAP_USER_SEARCH_BASE=OU=Usuarios,DC=ute,DC=edu,DC=ec
```

La cuenta de servicio solo necesita permiso de lectura para buscar usuarios.

---

## Comandos

```bash
make help          # lista todos

make up            # levantar
make down          # detener
make logs          # seguir los registros
make ps            # estado de los servicios

make seed          # permisos, roles y superusuario (idempotente)
make seed-demo     # datos de prueba
make migrate       # aplicar migraciones
make psql          # consola de la base
make dump          # respaldo comprimido en ./backups

make test              # pruebas del backend
make test-integracion  # las de integracion, sobre una base desechable
make lint              # ruff + mypy
```

> **Por que dos objetivos.** Las pruebas de integracion recrean el esquema
> entero antes de cada modulo. Se niegan a correr contra una base cuyo nombre no
> termine en `_test` —`make test` simplemente las omite— porque hacerlo contra
> la base de desarrollo borra los datos. `make test-integracion` crea
> `<base>_test` y apunta ahi.

---

## Produccion

### 1. Configurar

```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<secreto real>
POSTGRES_PASSWORD=<contrasena fuerte>
FIRST_SUPERUSER_PASSWORD=<contrasena fuerte>
CORS_ORIGINS=https://vice.ute.edu.ec       # solo https
SENESCYT_PROVIDER=manual                    # nunca mock
```

Con `ENVIRONMENT=production` la aplicacion **se niega a arrancar** si detecta
secretos de ejemplo, `DEBUG=true` o un origen CORS sin cifrar. Es intencional.

Ademas se desactivan `/docs`, `/redoc` y `/openapi.json`.

### 2. Construir las imagenes de produccion

Los `Dockerfile` tienen etapa `production`: el backend corre como usuario sin
privilegios y el frontend se sirve con nginx estatico.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

> El archivo `docker-compose.prod.yml` no viene incluido: depende de la
> infraestructura de la institucion (red, volumenes, secretos).

### 3. Proxy inverso

**El backend no debe exponerse directamente a internet.** Confia en la cabecera
`X-Forwarded-For` para registrar la IP del cliente, y sin un proxy delante esa
cabecera se puede falsear.

Configure TLS y HSTS en el proxy.

### 4. Verificar

```bash
curl https://vice.ute.edu.ec/health
```

Lista de verificacion completa en [`../SECURITY.md`](../SECURITY.md).

---

## Desarrollo sin contenedores

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ldap]"

export POSTGRES_HOST=localhost POSTGRES_PORT=5433
export PYTHONPATH=src

alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload --reload-dir src
```

### Frontend

```bash
cd frontend
npm install
npm start
```

---

## Problemas frecuentes

**El backend no arranca: «connection refused»**
PostgreSQL aun no termino de inicializar. En el primer arranque se reinicia una
vez tras crear la base. `make logs` y esperar.

**`make seed` falla por la contrasena**
`FIRST_SUPERUSER_PASSWORD` no cumple la politica. El mensaje dice cual regla
falta.

**La interfaz carga pero la API devuelve error de CORS**
`CORS_ORIGINS` no incluye el origen desde el que se abre la interfaz. Acepta
lista separada por comas: `http://localhost:4200,https://vice.ute.edu.ec`.

**El puerto 5433 esta ocupado**
Cambiar `POSTGRES_EXTERNAL_PORT` en `.env`.

**Las campanas no avanzan solas**
`SCHEDULER_ENABLED=false` es el valor por defecto. Actívelo conscientemente, o
use *Avanzar un paso* desde la interfaz.
