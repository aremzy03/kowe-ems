#!/usr/bin/env bash
# Run Phase 1 prerequisites, enough Assessment to recompute unpublished
# results, one tuition fee structure, then the Phase 5 Communications folder.
#
# Requires Django on {{baseUrl}} with config.settings.local.
# Does not start Celery. Notification logs stay queued unless a worker
# is already running; the collection accepts queued or sent.
# Does not run Finance invoice generate — that would skip creation here
# and would not queue a new invoice_generated log.
# Auth login / 2FA / teacher login are 5/min.
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

echo "Running EMS Phase 1 Auth against Local…"
bru run \
  "Auth" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

# login / 2FA / refresh share a 5/min IP throttle; Auth already uses the budget.
echo "Waiting 65s for auth throttle window before parent login…"
sleep 65

echo "Running parents + academics…"
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

# Parent login spent one auth slot. Teacher login is another login.
echo "Waiting 65s for auth throttle window before teacher login…"
sleep 65

echo "Running assessment setup through recompute (results stay unpublished)…"
bru run \
  "Assessment/01 Login Teacher.bru" \
  "Assessment/02 Create ClassSubjectAssignment.bru" \
  "Assessment/04 Set Valid Component Scheme.bru" \
  "Assessment/08 Teacher Bulk Upsert Scores.bru" \
  "Assessment/14 Recompute Class Results.bru" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

echo "Creating a tuition fee structure without generating invoices…"
bru run \
  "Finance/03 Create Fee Structure Tuition.bru" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

echo "Running Phase 5 Communications folder…"
bru run \
  "Communications" \
  -r \
  --env Local \
  --sandbox=developer \
  --bail \
  "$@"

echo "Phase 5 Bruno sequence complete."
echo "Not exercised here: Meta WhatsApp template approval, live SMTP, and a Celery worker."
echo "Without a worker, notification rows stay queued. Resend expects 400 unless a failed row exists."
echo "Assessment/20 still expects a parent PDF before the publish gate; this script does not run it."
