#!/usr/bin/env bash
set -euo pipefail

# Jalankan bot Telegram dan server webhook Pakasir dalam satu perintah.
# Variabel lingkungan opsional:
#   TELEGRAM_MODE        - auto|webhook|polling (default auto)
#   TELEGRAM_WEBHOOK_URL - URL publik webhook Telegram (digunakan pada mode webhook/auto)
#   PAKASIR_HOST         - host bind untuk server webhook (default 0.0.0.0)
#   PAKASIR_PORT         - port bind untuk server webhook (default 9000)

TELEGRAM_MODE="${TELEGRAM_MODE:-auto}"
TELEGRAM_MODE="$(echo "${TELEGRAM_MODE}" | tr '[:upper:]' '[:lower:]')"
TELEGRAM_WEBHOOK_URL="${TELEGRAM_WEBHOOK_URL:-}"
PAKASIR_HOST="${PAKASIR_HOST:-0.0.0.0}"
PAKASIR_PORT="${PAKASIR_PORT:-9000}"
BOT_CMD=(python -m src.main --mode "${TELEGRAM_MODE}")

case "${TELEGRAM_MODE}" in
  webhook)
    if [[ -z "${TELEGRAM_WEBHOOK_URL}" ]]; then
      echo "[run_stack] TELEGRAM_WEBHOOK_URL wajib di-set untuk mode webhook." >&2
      exit 1
    fi
    BOT_CMD=(python -m src.main --mode webhook --webhook-url "${TELEGRAM_WEBHOOK_URL}")
    ;;
  polling)
    BOT_CMD=(python -m src.main --mode polling)
    ;;
  auto|*)
    BOT_CMD=(python -m src.main --mode auto)
    if [[ -n "${TELEGRAM_WEBHOOK_URL}" ]]; then
      BOT_CMD+=("--webhook-url" "${TELEGRAM_WEBHOOK_URL}")
    fi
    ;;
esac

cleanup() {
  echo "[run_stack] Menangkap sinyal, menghentikan proses..."
  [[ -n "${BOT_PID:-}" ]] && kill "${BOT_PID}" 2>/dev/null || true
  [[ -n "${SERVER_PID:-}" ]] && kill "${SERVER_PID}" 2>/dev/null || true
  wait || true
}

trap cleanup INT TERM

echo "[run_stack] Menjalankan bot Telegram (mode: ${TELEGRAM_MODE})..."
"${BOT_CMD[@]}" &
BOT_PID=$!

echo "[run_stack] Menjalankan server webhook Pakasir di ${PAKASIR_HOST}:${PAKASIR_PORT} ..."
python -m src.server --host "${PAKASIR_HOST}" --port "${PAKASIR_PORT}" &
SERVER_PID=$!

wait -n
cleanup
