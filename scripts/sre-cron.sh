#!/usr/bin/env bash
set -euo pipefail

AUREA_BACKEND_URL="${AUREA_BACKEND_URL:-https://dils-wallet-production.up.railway.app}"
AUREA_CLIENT_URL="${AUREA_CLIENT_URL:-https://aurea-gold-client-production.up.railway.app}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}" # 5 min por padrão

echo "[SRE Cron] Iniciando loop. Intervalo: ${INTERVAL_SECONDS}s"
while true; do
  TS="$(date -Iseconds)"
  echo "[${TS}] Healthcheck…"
  # sanity
  if ! curl -fsS "${AUREA_BACKEND_URL}/healthz" >/dev/null; then FAIL=1; fi
  if ! curl -fsSI "${AUREA_CLIENT_URL}/" >/dev/null; then FAIL=1; fi

  # relatório do bot (saída rica + JSON)
  if aurea-sre bot; then
    echo "[${TS}] OK"
    FAIL=0
  else
    echo "[${TS}] FAIL detectado"
    FAIL=1
  fi

  # Alerta opcional (Telegram)
  if [ "${FAIL:-0}" = "1" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    MSG="Aurea SRE: Falha em produção. backend=${AUREA_BACKEND_URL} client=${AUREA_CLIENT_URL} @ $(date -Iseconds)"
    curl -fsS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${MSG}" >/dev/null || true
  fi

  sleep "${INTERVAL_SECONDS}"
done
