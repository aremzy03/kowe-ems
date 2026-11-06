# EMS API — Bruno collection (Phase 0–5)

Open this folder in Bruno (`File → Open Collection`) and select the **Local** environment.

## Prerequisites

1. Django running: `python manage.py runserver 127.0.0.1:8000` with `DJANGO_SETTINGS_MODULE=config.settings.local`
2. Tenant header: school requests send `X-Tenant-Slug: testacademy` (see `environments/Local.bru`). Do **not** use `Host: testacademy.localhost` to select a schema.
3. Copy `.env.example` → `.env` and set:
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` (from `create_test_tenant --admin-email …`)
   - `ADMIN_TOTP_SECRET` — base32 secret for the enrolled admin authenticator (from `/api/auth/2fa/enroll/` or your local TOTP device)
   - `PAYSTACK_SECRET_KEY` — must match the Django process key (HMAC for Finance webhooks)

### Phase 4 without a live Paystack `sk_test_` key

Start Django with a HMAC fixture secret and the local gateway stub:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.local
export PAYSTACK_SECRET_KEY=sk_test_bruno_local_hmac
export PAYSTACK_STUB_GATEWAY=True
python manage.py runserver 127.0.0.1:8000
```

Put the same `PAYSTACK_SECRET_KEY` in `bruno/.env`. Webhooks POST to the **same API host** with **no** `X-Tenant-Slug` (tenant is the Paystack subaccount code).

This proves resolve → subaccount → initialize → verify → signed webhook ×2 → unsigned/invalid HMAC locally. A live test-card checkout is still required before production (see Notes).

## Chained variables

| Variable | Set by |
|---|---|
| `accessToken` | Admin login + 2FA verify |
| `preAuthToken` | Admin/bursar password login when `requires_2fa` |
| `csrfToken` | Login `Set-Cookie: csrftoken` (used by refresh) |
| `inviteToken` | Parsed from invite `accept_url` |
| `teacherUserId` | Teacher invite accept (`Auth/04`) |
| `teacherAccessToken` | Teacher login (`Assessment/01` or `Attendance/01`) |
| `totpSecret` | Bursar 2FA enroll |
| `parentAccessToken` | Parent login |
| `linkingCode` / `studentId` / session–enrollment IDs | Academics CRUD |
| `component*Id` / `assignmentId` / score+audit counts | Assessment folder |
| `classTeacherAssignmentId` / `attendanceDate` / attendance+audit counts | Attendance folder |
| `unassignedArmId` / `attendanceUnlinkedStudentId` | Attendance RBAC negatives |
| `subaccountCode` / `parentInvoiceId` / `paymentReference` / `webhookRawBody` | Finance folder |
| `invoiceEmailNotificationId` / `manualPaymentId` / `paymentEmailNotificationId` | Communications invoice + cash receipt |
| `resultSummaryId` / `resultEmailNotificationId` / `resultWhatsappNotificationId` | Communications publish |
| `resendTargetId` / `resendExpectStatus` | Communications failed-list → resend (`200` if this run has a failed row, otherwise `400`) |

## Run end-to-end (CLI)

### Phase 1 only

```bash
cd bruno
cp -n .env.example .env   # then fill secrets
chmod +x scripts/run-phase1.sh
./scripts/run-phase1.sh
```

### Phase 1 + Phase 2 (assessment workflow)

```bash
cd bruno
chmod +x scripts/run-phase2.sh
./scripts/run-phase2.sh
```

### Phase 1 + Phase 2 + Phase 3 (attendance)

```bash
cd bruno
chmod +x scripts/run-phase3.sh
./scripts/run-phase3.sh
```

### Phase 1 + Phase 4 (finance / Paystack)

```bash
cd bruno
chmod +x scripts/run-phase4.sh
./scripts/run-phase4.sh
```

Does **not** re-login after Phase 1 (no extra 5/min throttle wait). Uses the admin / parent / bursar tokens from Auth.

### Phase 1 + assessment setup + Phase 5 (communications)

```bash
cd bruno
chmod +x scripts/run-phase5.sh
./scripts/run-phase5.sh
```

Does **not** run the full Finance folder (that generate is idempotent and would not queue a new invoice log). It creates one tuition `FeeStructure`, then the Communications folder. Celery is not started. Notification assertions accept `queued`, or `sent` when a worker happens to be up.

Or manually:

```bash
cd bruno
set -a && source .env && set +a
bru run \
  Auth \
  "Parents/01 Parent Signup.bru" \
  "Parents/02 Parent Login.bru" \
  "Parents/03 My Students Before Redeem.bru" \
  Academics \
  "Parents/04 Redeem Linking Code.bru" \
  "Parents/05 My Students After Redeem.bru" \
  Assessment \
  Attendance \
  Finance \
  -r --env Local --sandbox=developer --bail
```

That manual chain is Phases 1–4. It runs `Assessment/20` (parent PDF, which is 404 until publish) and Finance invoice generate. Phase 5 is `scripts/run-phase5.sh`, not this chain.

`--sandbox=developer` is required so TOTP and Paystack HMAC scripts can use Node `crypto`.

If Auth was just run, wait ~65s before Assessment/Attendance teacher login (shared 5/min throttle). Finance does not need that wait when run immediately after Phase 1 (no extra login).

## Folders

- **Auth** — admin 2FA login, staff invite create/accept, bursar 2FA enroll + confirm, cookie refresh
- **Parents** — self-signup, login, my-students empty → redeem → my-students linked
- **Academics** — Session → Term → ClassLevel → Arm → Subject → Student (captures `linkingCode`) → Enrollment
- **Assessment** (Phase 2) — ClassSubjectAssignment → weighted CA scheme → teacher bulk scores → **identical retry idempotency** → recompute → broadsheet → remarks → report card PDF → RBAC negatives
- **Attendance** (Phase 3) — set `Term.total_school_days` → ClassTeacherAssignment → teacher bulk attendance → **identical retry** (DailyAttendance + AttendanceAuditLog counts) → unassigned-class denial → register grid → term summaries (teacher / admin / parent linked + unlinked denied) → parent daily log → admin overview (date + term) → report card PDF with real attendance section
- **Finance** (Phase 4) — Paystack test bank `057` / `0000000000` onboarding → fee structures → class invoice generate (idempotent re-run) → parent initialize (pending, not paid) → **unsigned + invalid HMAC rejected** → verify apply → **same `charge.success` POST twice** (no double-credit) → bursar cash on a second student → collection dashboard → parent invoice list (own child only)
- **Communications** (Phase 5) — class invoice generate → `invoice_generated` email log (no WhatsApp: linked guardian phone is blank) → bursar cash on that invoice → `payment_confirmed` email log → parent results and PDF blocked before publish, visible after → `result_published` email and WhatsApp logs → `status=failed` list → resend (re-queue when a failed row from this run exists, otherwise 400 on the still-queued invoice email)

## Notes

- Auth login / 2FA verify / refresh are rate-limited (5/min). `scripts/run-phase2.sh` / `run-phase3.sh` wait 65s between Phase 1 auth and Assessment teacher login.
- Report card requests use `Accept: */*` (requesting only `application/pdf` can yield HTTP 406 from DRF content negotiation).
- Refresh uses the httpOnly `refresh_token` cookie (set on bursar enroll-confirm) plus `X-CSRFToken`.
- Admin Bearer `accessToken` from the start of Auth is kept for Academics/Assessment/Attendance/Finance (bursar tokens are stored separately as `bursarAccessToken`).
- Assessment idempotency: `Assessment/08` then `11`; snapshots `12`/`13` assert Score and AuditLog counts do not grow.
- Attendance idempotency: `Attendance/07` then `10`; snapshots `11`/`12` assert DailyAttendance and AttendanceAuditLog counts do not grow on identical retry.
- Attendance % denominator is explicit `Term.total_school_days` (`Attendance/02`), not an invented calendar.
- Report-card attendance content: `Attendance/27` downloads the PDF; `scripts/verify-report-card-attendance.sh` (run by `run-phase3.sh`) asserts the HTML source shows real days/percentage, not “Attendance data not available”.
- Finance webhook idempotency: `Finance/18` then `20` POST the **identical** raw `charge.success` body (HMAC-SHA512 of those bytes). Snapshots `17` / `19` / `21` assert `amount_paid` stays at the invoice total. `run-phase4.sh` then runs `prove_paystack_webhook_idempotency --deliver` (two more in-process POSTs + PlatformTransactionLog count).
- Finance unsigned/invalid HMAC: `Finance/12` and `14` must be HTTP 401 with invoice still unpaid (`13`, `15`).
- Live Paystack still needed for: real `/bank/resolve` + `/subaccount`, checkout with test card `4084084084084081`, and matching `PlatformTransactionLog` to the Paystack dashboard.
- Communications does not start Celery. Local email is the console backend and `WHATSAPP_BACKEND=console`. A stopped worker leaves logs `queued`. Do not treat that as a failed collection run.
- The parent who redeems the linking code gets a Guardian with a blank `phone_number`. The phone typed on student create stays on an unclaimed guardian, so invoice and payment notifications are email-only. Result publish still queues WhatsApp; a worker marks that row failed when the number is missing.
- `Assessment/20 Report Card Parent Linked Child` still expects HTTP 200. After the publish gate that PDF is 404 until an admin publishes, so `run-phase2.sh` stops there. Phase 5 covers the parent PDF in `Communications/07` (before) and `Communications/10` (after). `run-phase5.sh` recomputes results and does not run `Assessment/20`.
- WhatsApp template submission in Meta, live SMTP, and a running Celery worker are outside this collection.
