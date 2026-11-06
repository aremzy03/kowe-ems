#!/usr/bin/env bash
# Run Phase 1 prerequisites then Phase 2 Assessment Bruno sequence.
# Requires Django on {{baseUrl}} and Local env. Auth is rate-limited (5/min).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${ADMIN_EMAIL:?Set ADMIN_EMAIL in bruno/.env}"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD in bruno/.env}"
: "${ADMIN_TOTP_SECRET:?Set ADMIN_TOTP_SECRET in bruno/.env (enrolled admin TOTP)}"

echo "Running EMS Phase 1 prerequisites against Local…"
bru run \
  "Auth" \
  "Parents/01 Parent Signup.bru" \
  "Parents/02 Parent Login.bru" \
  "Parents/03 My Students Before Redeem.bru" \
  "Academics" \
  "Parents/04 Redeem Linking Code.bru" \
  "Parents/05 My Students After Redeem.bru" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

# login / 2FA / refresh share a 5/min IP throttle; Phase 1 already uses the budget.
echo "Waiting 65s for auth throttle window before Assessment teacher login…"
sleep 65

echo "Running Phase 2 Assessment folder…"
bru run \
  "Assessment" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"
