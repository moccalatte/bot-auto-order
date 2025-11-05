#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   BACKUP_ENCRYPTION_PASSWORD='rahasia' scripts/cron_backup.sh deployments/bot-myshop/compose.yml --offsite

COMPOSE_FILE=${1:-}
if [[ -z "${COMPOSE_FILE}" ]]; then
  echo "[cron_backup] argumen compose.yml wajib diisi." >&2
  exit 1
fi
shift || true

if [[ -z "${BACKUP_ENCRYPTION_PASSWORD:-}" ]]; then
  echo "[cron_backup] BACKUP_ENCRYPTION_PASSWORD belum di-set." >&2
  exit 1
fi

COMPOSE_BIN=${DOCKER_COMPOSE_BIN:-docker compose}

${COMPOSE_BIN} -f "${COMPOSE_FILE}" exec -T bot \
  BACKUP_ENCRYPTION_PASSWORD="${BACKUP_ENCRYPTION_PASSWORD}" \
  python -m src.tools.backup_manager create "$@"
