# EMS API — Bruno collection (Phase 0–2)

Open this folder in Bruno (`File → Open Collection`) and select the **Local** environment.

## Prerequisites

1. Django running: `python manage.py runserver 127.0.0.1:8000` with `DJANGO_SETTINGS_MODULE=config.settings.local`
2. Tenant host: requests send `Host: testacademy.localhost` (see `environments/Local.bru`)
3. Copy `.env.example` → `.env` and set:
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` (from `create_test_tenant --admin-email …`)
   - `ADMIN_TOTP_SECRET` — base32 secret for the enrolled admin authenticator (from `/api/auth/2fa/enroll/` or your local TOTP device)

## Chained variables

| Variable | Set by |
|---|---|
| `accessToken` | Admin login + 2FA verify |
| `preAuthToken` | Admin/bursar password login when `requires_2fa` |
| `csrfToken` | Login `Set-Cookie: csrftoken` (used by refresh) |
| `inviteToken` | Parsed from invite `accept_url` |
| `teacherUserId` | Teacher invite accept (`Auth/04`) |
| `teacherAccessToken` | Teacher login (`Assessment/01`) |
| `totpSecret` | Bursar 2FA enroll |
| `parentAccessToken` | Parent login |
| `linkingCode` / `studentId` / session–enrollment IDs | Academics CRUD |
| `component*Id` / `assignmentId` / score+audit counts | Assessment folder |

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
  -r --env Local --sandbox=developer --bail
```

`--sandbox=developer` is required so TOTP scripts can use Node `crypto`.

## Folders

- **Auth** — admin 2FA login, staff invite create/accept, bursar 2FA enroll + confirm, cookie refresh
- **Parents** — self-signup, login, my-students empty → redeem → my-students linked
- **Academics** — Session → Term → ClassLevel → Arm → Subject → Student (captures `linkingCode`) → Enrollment
- **Assessment** (Phase 2) — ClassSubjectAssignment → weighted CA scheme (reject bad / accept valid) → teacher bulk scores → **identical retry idempotency proof** (Score count + AuditLog) → recompute → broadsheet (teacher + admin) → remarks → report card PDF (parent linked OK / unlinked denied / teacher / admin) → **RBAC negatives**: unassigned-subject bulk-upsert + broadsheet denied for teacher; parent `results/student` denied for unlinked student (`24`–`28`)

## Notes

- Auth login / 2FA verify / refresh are rate-limited (5/min). `scripts/run-phase2.sh` waits 65s between Phase 1 auth and Assessment teacher login.
- Report card requests use `Accept: */*` (requesting only `application/pdf` can yield HTTP 406 from DRF content negotiation).
- Refresh uses the httpOnly `refresh_token` cookie (set on bursar enroll-confirm) plus `X-CSRFToken`.
- Admin Bearer `accessToken` from the start of Auth is kept for Academics/Assessment (bursar tokens are stored separately as `bursarAccessToken`).
- Idempotency check: `Assessment/08` then `Assessment/11` re-submit the same bulk payload; `12`/`13` assert Score and AuditLog counts do not grow.
