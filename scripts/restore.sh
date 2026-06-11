#!/usr/bin/env bash
#
# Restauration des données HealthAI depuis une sauvegarde produite par backup.sh.
#
# ⚠️  Opération DESTRUCTIVE : écrase les données actuelles (Postgres, MongoDB,
#     modèles ML). Une confirmation est demandée (sauf si FORCE=1).
#
# Usage :
#   ./scripts/restore.sh                      # restaure la sauvegarde la plus récente
#   ./scripts/restore.sh backups/20260611_103000
#   FORCE=1 ./scripts/restore.sh <dossier>    # sans confirmation interactive
#
# Variables d'environnement : identiques à backup.sh (PG_*, MONGO_*, MODELS_VOLUME).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
cd "$INFRA_DIR"

PG_SERVICE="${PG_SERVICE:-db}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-healthai}"
MONGO_SERVICE="${MONGO_SERVICE:-mongodb}"
MONGO_DB="${MONGO_DB:-recommendation_db}"
PROJECT="$(basename "$INFRA_DIR" | tr '[:upper:]' '[:lower:]')"
MODELS_VOLUME="${MODELS_VOLUME:-${PROJECT}_recommendation_models}"
BACKUP_ROOT="${BACKUP_ROOT:-$INFRA_DIR/backups}"

dc() { docker compose "$@"; }

# --- Sélection de la sauvegarde (argument, sinon la plus récente) ---
if [ "$#" -ge 1 ]; then
  SRC="$1"
else
  # shellcheck disable=SC2012
  SRC="$(ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | head -n1 || true)"
fi
SRC="${SRC%/}"
if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "✗ Aucune sauvegarde trouvée (cherché dans : $BACKUP_ROOT)." >&2
  echo "  Précise un dossier : ./scripts/restore.sh <dossier_de_sauvegarde>" >&2
  exit 1
fi

echo "==> Restauration depuis : $SRC"
[ -f "$SRC/MANIFEST.txt" ] && { echo "--- MANIFEST ---"; cat "$SRC/MANIFEST.txt"; echo "----------------"; }

# --- Confirmation (écrasement) ---
if [ "${FORCE:-0}" != "1" ]; then
  printf "⚠️  Cette opération ÉCRASE les données actuelles. Continuer ? [y/N] "
  read -r ans
  case "$ans" in
    y | Y | yes | YES | oui | OUI) ;;
    *) echo "Annulé." ; exit 0 ;;
  esac
fi

# --- Vérification : Postgres doit tourner ---
if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$PG_SERVICE"; then
  echo "✗ Le service Postgres '$PG_SERVICE' ne tourne pas. Lance d'abord : docker compose up -d" >&2
  exit 1
fi

# --- 1. PostgreSQL ---
PG_FILE="$SRC/postgres_${PG_DB}.dump"
if [ -f "$PG_FILE" ]; then
  echo "--> PostgreSQL ($PG_DB)..."
  # --clean --if-exists : supprime/recrée les objets ; --no-owner : ignore les rôles absents.
  # pg_restore peut émettre des avertissements bénins -> on ne casse pas le script dessus.
  dc exec -T "$PG_SERVICE" pg_restore -U "$PG_USER" -d "$PG_DB" \
    --clean --if-exists --no-owner < "$PG_FILE" || echo "    (avertissements pg_restore ignorés)"
  echo "    OK"
else
  echo "--> PostgreSQL : '$PG_FILE' absent, ignoré"
fi

# --- 2. MongoDB ---
MONGO_FILE="$SRC/mongo_${MONGO_DB}.archive.gz"
if [ -f "$MONGO_FILE" ]; then
  if docker compose ps --status running --services 2>/dev/null | grep -qx "$MONGO_SERVICE"; then
    echo "--> MongoDB ($MONGO_DB)..."
    # --drop : vide les collections cibles avant restauration.
    dc exec -T "$MONGO_SERVICE" mongorestore --drop --gzip --archive < "$MONGO_FILE"
    echo "    OK"
  else
    echo "--> MongoDB : service '$MONGO_SERVICE' arrêté, restauration ignorée"
  fi
else
  echo "--> MongoDB : '$MONGO_FILE' absent, ignoré"
fi

# --- 3. Modèles ML (volume Docker) ---
MODELS_FILE="$SRC/recommendation_models.tar.gz"
if [ -f "$MODELS_FILE" ]; then
  if docker volume inspect "$MODELS_VOLUME" >/dev/null 2>&1; then
    echo "--> Modèles ML (volume $MODELS_VOLUME)..."
    docker run --rm -v "$MODELS_VOLUME":/data -v "$SRC":/backup:ro alpine \
      sh -c 'rm -rf /data/* /data/..?* 2>/dev/null; tar xzf /backup/recommendation_models.tar.gz -C /data'
    echo "    OK (redémarre le service : docker compose restart recommendation)"
  else
    echo "--> Modèles ML : volume '$MODELS_VOLUME' introuvable, ignoré"
  fi
else
  echo "--> Modèles ML : archive absente, ignoré"
fi

echo "==> Restauration terminée."
