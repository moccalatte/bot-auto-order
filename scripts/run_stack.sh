#!/usr/bin/env bash
set -euo pipefail

# Jalankan bot Telegram dan server webhook Pakasir dalam satu perintah.
# Variabel lingkungan opsional:
#   TELEGRAM_WEBHOOK_URL - URL publik webhook Telegram (wajib saat mode webhook)
#   PAKASIR_HOST         - host bind untuk server webhook (default 0.0.0.0)
#   PAKASIR_PORT         - port bind untuk server webhook (default 9000)

TELEGRAM_WEBHOOK_URL="${TELEGRAM_WEBHOOK_URL:-}"
PAKASIR_HOST="${PAKASIR_HOST:-0.0.0.0}"
PAKASIR_PORT="${PAKASIR_PORT:-9000}"

if [[ -z "${TELEGRAM_WEBHOOK_URL}" ]]; then
  echo "[run_stack] TELEGRAM_WEBHOOK_URL belum di-set. Contoh: export TELEGRAM_WEBHOOK_URL=https://example.com/telegram" >&2
  exit 1
fi

cleanup() {
  echo "[run_stack] Menangkap sinyal, menghentikan proses..."
  [[ -n "${BOT_PID:-}" ]] && kill "${BOT_PID}" 2>/dev/null || true
  [[ -n "${SERVER_PID:-}" ]] && kill "${SERVER_PID}" 2>/dev/null || true
  wait || true
}

trap cleanup INT TERM

echo "[run_stack] Menjalankan bot Telegram (webhook mode)..."
python -m src.main --webhook --webhook-url "${TELEGRAM_WEBHOOK_URL}" &
BOT_PID=$!

echo "[run_stack] Menjalankan server webhook Pakasir di ${PAKASIR_HOST}:${PAKASIR_PORT} ..."
python -m src.server --host "${PAKASIR_HOST}" --port "${PAKASIR_PORT}" &
SERVER_PID=$!

wait -n
cleanup
