#!/usr/bin/env bash
# =====================================================================
# Despliegue en el VPS — UTE Vice · Gestion Academica
# =====================================================================
# Lo ejecuta el flujo de GitHub Actions por SSH, despues de haber copiado
# el codigo y el frontend ya compilado. Tambien sirve a mano.
#
# Es idempotente: se puede repetir sin efectos acumulativos.
# =====================================================================
set -Eeuo pipefail

RAIZ="${RAIZ:-/opt/vice-gestion}"
COMPOSE="docker compose -f docker-compose.prod.yml"
SALUD="http://127.0.0.1:${BACKEND_EXTERNAL_PORT:-8100}/health"

cd "$RAIZ"

paso() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

# --- El .env es el unico estado que no viaja con el despliegue -------
if [[ ! -f .env ]]; then
  echo "FALTA $RAIZ/.env — se aborta antes de tocar nada." >&2
  exit 1
fi

paso "Imagen del backend"
$COMPOSE build backend

# --- Respaldo previo -------------------------------------------------
# Antes de aplicar migraciones, por si alguna sale mal. Se conservan los
# siete ultimos: en un disco compartido no se acumulan indefinidamente.
if $COMPOSE ps --status running --services 2>/dev/null | grep -qx postgres; then
  paso "Respaldo de la base"
  mkdir -p respaldos
  ARCHIVO="respaldos/previo-$(date +%Y%m%d-%H%M%S).sql.gz"
  set +e
  $COMPOSE exec -T postgres pg_dump -U "$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2)" \
      "$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2)" 2>/dev/null | gzip > "$ARCHIVO"
  CODIGO=${PIPESTATUS[0]}
  set -e
  if [[ $CODIGO -eq 0 ]]; then
    echo "   $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"
    ls -1t respaldos/previo-*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm --
  else
    rm -f "$ARCHIVO"
    echo "   sin respaldo: la base aun no responde (primer despliegue)"
  fi
fi

# --- Arranque --------------------------------------------------------
# `up` aplica las migraciones: es el `command` del servicio.
paso "Levantando servicios"
$COMPOSE up -d --remove-orphans

paso "Esperando al backend"
for intento in $(seq 1 40); do
  if curl -fsS --max-time 3 "$SALUD" >/dev/null 2>&1; then
    echo "   responde tras ${intento} intento(s)"
    break
  fi
  if [[ $intento -eq 40 ]]; then
    echo "El backend no respondio en 80 s. Ultimos registros:" >&2
    $COMPOSE logs --tail 40 backend >&2
    exit 1
  fi
  sleep 2
done

# --- Roles, permisos y superusuario: idempotente ---------------------
paso "Sembrando roles y permisos"
$COMPOSE exec -T backend python -m app.cli seed

# --- Imagenes viejas -------------------------------------------------
# Solo las sueltas de este proyecto; el VPS aloja otras aplicaciones y un
# `prune` general se llevaria por delante lo que no es nuestro.
paso "Limpiando imagenes huerfanas del proyecto"
docker image prune -f --filter "label=com.docker.compose.project=ute-vice" >/dev/null || true

paso "Estado"
$COMPOSE ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
curl -fsS "$SALUD" && echo
echo
echo "Despliegue completo."
