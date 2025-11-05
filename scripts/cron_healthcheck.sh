#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/cron_healthcheck.sh deployments/bot-myshop/compose.yml
# Optional env vars:
#   DOCKER_COMPOSE_BIN (default: docker compose)

COMPOSE_FILE=${1:-}
if [[ -z "${COMPOSE_FILE}" ]]; then
  echo "[cron_healthcheck] argumen compose.yml wajib diisi." >&2
  exit 1
fi

COMPOSE_BIN=${DOCKER_COMPOSE_BIN:-docker compose}

${COMPOSE_BIN} -f "${COMPOSE_FILE}" exec -T bot python -m src.tools.healthcheck
