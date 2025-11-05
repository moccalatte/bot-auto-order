#!/usr/bin/env bash
set -euo pipefail

TENANT_DIR=${1:-.}
ENV_FILE=${ENV_FILE:-bot.env}
COMPOSE_FILE=${COMPOSE_FILE:-compose.yml}

cd "${TENANT_DIR}" >/dev/null 2>&1 || {
  echo "[run_tenant] folder ${TENANT_DIR} tidak ditemukan" >&2
  exit 1
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[run_tenant] file ${ENV_FILE} belum ada. Isi cred dulu." >&2
  exit 1
}

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "[run_tenant] file ${COMPOSE_FILE} tidak ditemukan." >&2
  exit 1
}

# Muat environment dari bot.env agar variabel penting tersedia
set -a
source "${ENV_FILE}"
set +a

export BOT_WEBHOOK_PORT="${BOT_WEBHOOK_PORT:-8080}"
export PAKASIR_PORT="${PAKASIR_PORT:-9000}"
export IMAGE_NAME="${IMAGE_NAME:-bot-auto-order:latest}"

echo "[run_tenant] Menjalankan docker compose dengan IMAGE_NAME=${IMAGE_NAME}, BOT_WEBHOOK_PORT=${BOT_WEBHOOK_PORT}, PAKASIR_PORT=${PAKASIR_PORT}"

docker compose -f "${COMPOSE_FILE}" up -d

echo "[run_tenant] Selesai. Gunakan 'docker compose -f ${COMPOSE_FILE} ps' untuk cek status."
