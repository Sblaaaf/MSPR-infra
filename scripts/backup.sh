#!/usr/bin/env bash
#
# Sauvegarde des données HealthAI.
#
# Couvre les trois magasins de données persistants de la stack :
#   - PostgreSQL  (base `healthai`)         -> auth, meal, kcal, etl, admin
#   - MongoDB     (base `recommendation_db`) -> recommendation
#   - Volume Docker `recommendation_models`  -> modèles ML entraînés (optionnel)
#
# Les dumps sont générés DANS les conteneurs (pg_dump / mongodump) puis
# rapatriés via stdout dans un dossier horodaté : backups/<AAAAMMJJ_HHMMSS>/.
#
# Usage :
#   ./scripts/backup.sh
#
# Variables d'environnement (toutes optionnelles) :
#   BACKUP_ROOT    répertoire racine des sauvegardes   (défaut: ./backups)
#   BACKUP_KEEP    nombre de sauvegardes à conserver    (défaut: 7)
#   PG_SERVICE / PG_USER / PG_DB                         (défaut: db / postgres / healthai)
#   MONGO_SERVICE / MONGO_DB                             (défaut: mongodb / recommendation_db)
#   MODELS_VOLUME  volume Docker des modèles ML          (défaut: <projet>_recommendation_models)
#
set -euo pipefail

# --- Localisation : on se place dans le repo infra (parent de scripts/) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
cd "$INFRA_DIR"

# --- Réglages ---
PG_SERVICE="${PG_SERVICE:-db}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-healthai}"
MONGO_SERVICE="${MONGO_SERVICE:-mongodb}"
MONGO_DB="${MONGO_DB:-recommendation_db}"
# Nom du projet compose (= nom du dossier, en minuscules) pour préfixer le volume
PROJECT="$(basename "$INFRA_DIR" | tr '[:upper:]' '[:lower:]')"
MODELS_VOLUME="${MODELS_VOLUME:-${PROJECT}_recommendation_models}"

BACKUP_ROOT="${BACKUP_ROOT:-$INFRA_DIR/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"
TS="$(date +%Y%m%d_%H%M%S)"
DEST="$BACKUP_ROOT/$TS"

dc() { docker compose "$@"; }

# --- Vérifications préalables ---
if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$PG_SERVICE"; then
  echo "✗ Le service Postgres '$PG_SERVICE' ne tourne pas. Lance d'abord : docker compose up -d" >&2
  exit 1
fi

mkdir -p "$DEST"
echo "==> Sauvegarde HealthAI ($TS)"
echo "    destination : $DEST"

# --- 1. PostgreSQL (format custom -Fc, restaurable via pg_restore) ---
echo "--> PostgreSQL ($PG_DB)..."
dc exec -T "$PG_SERVICE" pg_dump -U "$PG_USER" -d "$PG_DB" -Fc > "$DEST/postgres_${PG_DB}.dump"
echo "    OK ($(du -h "$DEST/postgres_${PG_DB}.dump" | cut -f1))"

# --- 2. MongoDB (archive gzip) ---
if docker compose ps --status running --services 2>/dev/null | grep -qx "$MONGO_SERVICE"; then
  echo "--> MongoDB ($MONGO_DB)..."
  dc exec -T "$MONGO_SERVICE" mongodump --db "$MONGO_DB" --archive --gzip > "$DEST/mongo_${MONGO_DB}.archive.gz"
  echo "    OK ($(du -h "$DEST/mongo_${MONGO_DB}.archive.gz" | cut -f1))"
else
  echo "--> MongoDB : service '$MONGO_SERVICE' arrêté, ignoré"
fi

# --- 3. Modèles ML (volume Docker) — optionnel, régénérable via train.py ---
if docker volume inspect "$MODELS_VOLUME" >/dev/null 2>&1; then
  echo "--> Modèles ML (volume $MODELS_VOLUME)..."
  docker run --rm -v "$MODELS_VOLUME":/data:ro -v "$DEST":/backup alpine \
    tar czf "/backup/recommendation_models.tar.gz" -C /data . 2>/dev/null
  echo "    OK ($(du -h "$DEST/recommendation_models.tar.gz" | cut -f1))"
else
  echo "--> Modèles ML : volume '$MODELS_VOLUME' introuvable, ignoré"
fi

# --- Manifeste ---
cat > "$DEST/MANIFEST.txt" <<EOF
HealthAI — sauvegarde
date           : $TS
postgres ($PG_DB)        -> postgres_${PG_DB}.dump        (pg_dump -Fc)
mongodb  ($MONGO_DB)     -> mongo_${MONGO_DB}.archive.gz  (mongodump --archive --gzip)
modèles ML               -> recommendation_models.tar.gz  (si volume présent)

Restauration : ./scripts/restore.sh "$DEST"
EOF

# --- Rotation : on ne garde que les BACKUP_KEEP plus récentes ---
if [ "$BACKUP_KEEP" -gt 0 ]; then
  # shellcheck disable=SC2012
  ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | tail -n "+$((BACKUP_KEEP + 1))" | while read -r old; do
    echo "--> Rotation : suppression de l'ancienne sauvegarde $(basename "$old")"
    rm -rf "$old"
  done
fi

echo "==> Terminé. Sauvegarde complète dans : $DEST"
