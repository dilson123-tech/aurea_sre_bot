#!/usr/bin/env bash
set -euo pipefail
AUREA_BACKEND_URL="https://dils-wallet-production.up.railway.app"
AUREA_CLIENT_URL="https://aurea-gold-client-production.up.railway.app"

# sanity antes do bot
curl -fsS "$AUREA_BACKEND_URL/healthz" >/dev/null
curl -fsSI "$AUREA_CLIENT_URL/"      >/dev/null

aurea-sre bot
