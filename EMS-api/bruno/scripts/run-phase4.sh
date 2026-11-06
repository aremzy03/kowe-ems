#!/usr/bin/env bash
# Run Phase 1 prerequisites, then Phase 4 Finance Bruno sequence.
# Requires Django on {{baseUrl}} with config.settings.local.
#
# Local HMAC fixtures (no live sk_test_ card): start Django with
#   PAYSTACK_SECRET_KEY=sk_test_bruno_local_hmac
#   PAYSTACK_STUB_GATEWAY=True
# and put the same PAYSTACK_SECRET_KEY in bruno/.env.
# Auth login / 2FA is 5/min — this script does not re-login after Phase 1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
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
: "${PAYSTACK_SECRET_KEY:?Set PAYSTACK_SECRET_KEY in bruno/.env (HMAC fixture or live sk_test_)}"

echo "Running EMS Phase 1 Auth against Local…"
bru run \
  "Auth" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

# login / 2FA / refresh share a 5/min IP throttle; Auth already uses the budget
# (admin login + bursar login + refresh). Parent login is next.
echo "Waiting 65s for auth throttle window before parent login…"
sleep 65

echo "Running Phase 1 parents + academics…"
bru run \
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

echo "Running Phase 4 Finance folder (Paystack test bank 057 / 0000000000)…"
bru run \
  "Finance" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

echo "Proving double-webhook + unsigned HMAC against the tenant DB…"
cd "$REPO"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
.venv/bin/python manage.py prove_paystack_webhook_idempotency \
  --schema testacademy \
  --from-bruno-env \
  --deliver

echo "Phase 4 Bruno sequence complete."
echo "Still needs a live sk_test_ card flow: real GET /bank/resolve, POST /subaccount,"
echo "checkout with test card 4084084084084081, and Paystack dashboard vs PlatformTransactionLog."
