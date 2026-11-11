# EMS-api changelog

Status snapshot as of **2026-11-11** (school-wide fees, combined Paystack checkout, generate-all-classes, pytest on SQLite). Earlier the same file recorded **2026-11-06** evening: memberships directory, guardians/linking codes, payment ledger, `/auth/me`, protected destroys, assessment scheme list filters. This is the current state of the Django API, not a release history. Phases 0–5 are implemented in code. Several exit checks are still manual or live-only.

Playbooks: `EMS-Phase0-Init-Playbook.md` through `EMS-Phase5-Init-Playbook.md`. Bruno collection: `bruno/` (Phases 0–5).

## Current state

Schema-per-tenant (`django-tenants`). One API host. The school schema comes from the JWT `tenant_schema` claim, then `X-Tenant-Slug`. `Host` does not select a tenant (Option B / Phase 0.1).

Local settings: `config.settings.local`. Postgres for this machine is the `ems-api_db_1` container on host port **5433**. Redis is already on **6379**. Unit tests do not use that database. From `EMS-api`, `python -m pytest` loads `config.settings.test` and a temporary SQLite file (`config.db.sqlite_tenant`). **296 passed**, 4 subtests, on 2026-11-11. `manage.py test` against Postgres still cannot `CREATE DATABASE` (`dev_user` lacks `CREATEDB`).

Local schools present: `testacademy`, `testacademy2`. `testacademy` has an active admin (`admin@testacademy.local`) plus teacher, bursar, and parent accounts from the browser walks.

| Phase | Scope | Code |
|---|---|---|
| 0 | Tenants, shared `User`, JWT cookie auth, Docker Compose, CORS, auth throttle, Sentry in production | Built |
| 0.1 | `HeaderTenantMiddleware` | Built |
| 1 | RBAC, staff invites, admin/bursar TOTP, parent signup, linking codes, academic structure | Built |
| 2 | Weighted components, idempotent scores, recompute/ranking, broadsheet, WeasyPrint report cards | Built |
| 3 | Class-teacher attendance, term summary, attendance on the report card | Built |
| 4 | Bank resolve before subaccount, fees, invoices, Paystack initialize/verify, signed webhook, manual cash, platform revenue | Built |
| 5 | Notifications: Celery, email, WhatsApp, publish gate, invoice/payment signals, admin delivery API, Bruno | Built in code. Live checks below are open |

`communications` is no longer an empty app.

## Finance billing (2026-11-11)

Migration `finance.0005_schoolwide_fees_and_combined_checkout` is applied on the app database (public schema and each tenant schema).

### School-wide fees

- `FeeStructure.class_level` is nullable. Empty means the fee applies to every class in that term (textbook, uniform, bus, excursion).
- Class fees for one class and term are still one itemized invoice. Each school-wide fee is its own invoice, so it can be paid alone or in a combined checkout.
- Uniqueness: the existing `(class_level, term, name)` constraint, plus a partial unique constraint on `(term, name)` where `class_level` is null. The serializer rejects a second school-wide fee with the same term and name (Postgres treats those nulls as distinct).
- `Invoice` no longer has a unique `(student, term)` constraint. A student can have several invoices in one term.
- Generation is idempotent by fee line item, not by “any invoice for the term”. Active enrollment rows are locked with `select_for_update`. A re-run bills only new students or new fees.

### Generate for every class

- `POST /api/finance/invoices/generate/` still takes `class_level` + `term` for one class. Admin or bursar with confirmed TOTP.
- Omit `class_level`, or send null, to bill every class with active enrollments in that term. Classes run in name order inside one transaction. A class with no class fees and no school-wide fee is skipped. A school-wide fee already billed to a student is not billed again. **400** when no enrolled class has anything to bill. The response shape is unchanged: `created_count`, `skipped_count`, `skipped_student_ids`, `invoices`.

### Combined Paystack checkout

- Initialize accepts either `invoice` (optional partial `amount`, in naira) or `invoices` (at least two ids). A bundle rejects `amount` and pays each invoice’s full outstanding.
- One `PaymentCheckout` (`reference` `pay_{uuid}`, total amount) and one pending `Payment` per invoice, linked by `Payment.checkout`.
- The parent must be linked to every student on the bundle. Otherwise **404** and nothing is created.
- `verify_and_apply_payment` is still the only Paystack apply path. A checkout reference marks each child payment, recomputes each invoice, and writes one `PlatformTransactionLog` for the checkout total. Verifying the same reference again does not call Paystack. A kobo mismatch fails the checkout and its non-success children.
- Starting a new checkout for an invoice that already has a pending Paystack payment fails that checkout and its sibling pending rows.

### Settlement account

- `SchoolPaymentAccountView` permission is `IsAdminOrBursar`. A bursar with confirmed TOTP can onboard. A teacher still gets **403**. A second onboard is still **409**.

## Gap closure (2026-11-06 evening)

Work that closed the earlier “Not in this API” / incomplete-CRUD gaps. Live smoke on `testacademy`. The suites below now run with `python -m pytest` on SQLite (they do not need `CREATEDB`).

### Memberships and invites

- **Staff directory.** `GET/PATCH/PUT/DELETE /api/memberships/members/` (`SchoolMembershipViewSet`). School admin + TOTP when `REQUIRE_ADMIN_2FA` is on. Default list is staff roles only (admin / teacher / bursar); parents omitted unless `?role=` is set. Also `?is_active=true|false`. Response includes membership `id`, `user` (User UUID for assignment pickers), email, names, `role`, `is_active`, `joined_at`.
- **Soft deactivate.** `DELETE` sets `is_active=false` and does not delete the public `User`. Last active admin cannot be demoted or deactivated.
- **Invite inbox.** `GET /api/memberships/invites/` (pending by default; `?status=` for accepted/expired). `GET …/{id}/`. `DELETE …/{id}/` revokes pending → `status=expired`. Raw invite **token is withheld** on list/retrieve. Create + accept are unchanged (`POST /invites/`, `POST /invites/accept/`). Stale pending invites are marked expired on list.
- Create membership still happens only via invite-accept / parent signup (no unrestricted membership create).

### Guardians and linking codes

- **Guardians.** `GET/POST /api/academics/guardians/`, `GET/PATCH/PUT/DELETE /api/academics/guardians/{id}/`. Admin only. `Guardian` has no email column; linked parent email is read-only `user_email` after signup/redeem. Delete is **409** while any `StudentGuardianLink` exists (API refuses cascade wipe).
- **Links.** `GET/POST /api/academics/guardian-links/` (`?student=`, `?guardian=`), `PATCH` for `is_primary_contact` (promoting one demotes others), `DELETE` to unlink.
- **Regenerate linking code.** `POST /api/academics/students/{id}/regenerate-linking-code/` marks unused codes used (`used_by=null`) and issues a new unused code via `Student.generate_unused_linking_code()`. Redeem is unchanged. Student list/retrieve still expose the current unused `linking_code`; create/retrieve also return nested `guardian_links`.

### Finance ledger

- **Payments.** `GET /api/finance/payments/` and `GET /api/finance/payments/{id}/` for admin/bursar + TOTP. `{ count, results }`. Filters: `?invoice=`, `?status=` (`pending`/`success`/`failed`), `?term=` via invoice FK. `DELETE` → **405**. Create remains initialize / verify / manual.
- **Invoice retrieve.** `GET /api/finance/invoices/{id}/` with nested `payments`. Staff list is unchanged.
- **Parent invoices.** `GET /api/finance/my-invoices/` now includes nested `payments`. Invoice `status` / `amount_paid` still count **SUCCESS** only; pending Paystack rows stay `pending` with `paid_at: null`.

### Auth profile

- **`GET /api/auth/me/`.** Authenticated; any active school member (not admin-only, not 2FA-gated). Tenant from JWT / `X-Tenant-Slug` (Option B). Returns `id`, `email`, `first_name`, `last_name`, `role`, `membership_id`, `is_active`, `tenant_schema`, `tenant_slug`, `school_name`. Platform admin on the public schema gets `role: platform_admin`, null membership/slug/school_name. Unauthenticated → 401; no active membership in the resolved tenant → 403.
- Successful login and 2FA token responses also include a nested `"me"` object. The shell still refetches `me` after refresh as source of truth.

### Academics destroy behaviour

- **`ProtectedDestroyMixin`** on sessions, terms, class levels, arms, subjects, students, enrollments so PROTECT FK conflicts return **409** with a readable message instead of 500 (aligned with fee-structure destroy).

### Assessment scheme filters

- **Component list** accepts `?subject=`, `?class_level=`, `?term=` so an admin UI can load one scheme. `POST …/set-scheme/` and `POST …/clone-scheme/` were already present; destroy still blocked unless remaining weights are 0 or 100%.

## Phase 5 (2026-11-06)

- **NotificationLog** (tenant schema): recipient, channel `email` / `whatsapp`, trigger `invoice_generated` / `payment_confirmed` / `result_published`, status `queued` / `sent` / `failed`.
- **Celery** app `ems`, `docker-compose` worker, task `send_notification(notification_log_id, schema_name)`. Eager mode is off. Transient failures retry (3 attempts). Permanent failures fail immediately.
- **Email** queues on the task. Local backend is console. Production is generic SMTP env vars. Result mail links to `/parent/results` and does not include scores.
- **WhatsApp** queues on the same task. Local `WHATSAPP_BACKEND=console`. Production calls the Cloud API with `requests` (no BSP SDK). Bulk sends are spaced 6 seconds apart. A bad number fails that log only.
- **Publish gate.** `TermResultSummary.is_published` defaults to false. `POST /api/assessment/results/publish/` (school admin with confirmed TOTP). Until publish, a parent’s results payload is empty and the report-card PDF is 404. Staff can still read unpublished results. Publish queues email and WhatsApp once, on commit.
- **Signals.** A new invoice, and a payment whose status becomes `success`, queue email after commit. WhatsApp is included when `Guardian.phone_number` is non-blank. A later save does not send again. Result alerts are not sent from these signals.
- **Admin API.** `GET /api/communications/notifications/` and `POST /api/communications/notifications/{id}/resend/`. Resend is only for `failed`, and it re-queues the same row.

Tests recorded during the build: communications 66 passed after the admin API; finance + communications + publication **169 passed** after the signals. Bruno parsed the 14 new `bruno/Communications/` requests.

## Same-day additions (2026-11-06, after Phase 5, before gap closure)

- **Staff invoices.** `GET /api/finance/invoices/` for admin or bursar. Optional `?term=` and `?class_level=`. Response is `{ count, results }` using `InvoiceSerializer`. Parent `my-invoices/` was later enriched with nested payments (see Gap closure).
- **Platform directory reads.** `GET /api/platform/tenants/` (schools only; the public-schema row is omitted) and `GET /api/platform/webhooks/` (newest 100 `WebhookLog` rows; `error_message` clipped to 280 characters, `payload_preview` to 200; raw `payload` is not returned). Both are `IsPlatformAdmin` and stay on the public schema. They do not provision a school or replay a delivery. Revenue and `POST /api/webhooks/paystack/` are unchanged.
- **Term reads.** `GET /api/academics/terms/` list and retrieve are any active school member. Writes stay admin-only. Class level, arm, and subject list/retrieve stay admin or teacher.
- **Django admin.** `http://127.0.0.1:8000/admin/` was already mounted. `/admin` and `/admin/` are public-path prefixes, so they do not 400 for a missing `X-Tenant-Slug`. Public-schema requests set `request.tenant` to the public `Tenant` row, or to django-tenants’ `FakeTenant` when that row is missing, because the admin index calls `is_public_schema` and crashes on `None`. Every concrete model in accounts, platform_admin, memberships, academics, assessment, attendance, finance (including `InvoiceLineItem`), communications, and `otp_totp.TOTPDevice` is registered. Secrets stay off the changelist. School-schema rows resolve only when the connection is that tenant. Login requires `is_staff`; a school admin is not enough. `platform_admin.test_tenant_resolution`: 22 passed (`--keepdb`) after the tenant bind. `manage.py check`: no issues.

A browser walk on `testacademy` the same day published JSS1 A (1st term, 2026/2027), downloaded the report-card PDF (200, 15,680 bytes), and recorded a ₦50,000 cash payment. A Celery worker moved `invoice_generated` and `payment_confirmed` email rows to **sent** (console backend). Publish did not queue a notification because it ran before the parent account existed. The worker was shut down afterward; it is not left running.

## Needs doing

- Submit the three Utility templates in WhatsApp Manager before live Cloud API sends: `kowe_invoice_generated`, `kowe_payment_confirmed`, `kowe_result_published` (`communications/whatsapp_templates.py`).
- Set production `EMAIL_*` and `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` when those channels go live.
- Run a Celery worker in any environment where rows should leave `queued`.
- Point `bruno/.env` at the `testacademy` admin (`admin@testacademy.local` plus that user’s TOTP secret) and rerun `bruno/scripts/run-phase5.sh`. The earlier live run stopped at login with **401** when the schema had no memberships. That membership now exists. The Bruno suite has not been rerun.
- Update `bruno/Assessment/20` so `run-phase2.sh` does not expect a parent PDF with HTTP 200 before publish. Phase 5 covers that PDF in `Communications/07` (404) and `Communications/10` (200).
- `manage.py test` on Postgres still needs `CREATEDB` or an existing `test_ems_db`. The pytest suite does not: it uses SQLite and does not open the app database.
- Optionally gate `platform_admin` behind `REQUIRE_ADMIN_2FA` the same way school admin/bursar are. The platform frontend now handles `requires_2fa`; the live API still returns tokens immediately for platform operators when that flag is off / role is outside the 2FA set.

## Needs confirming

- [ ] Phase 5 exit list in the playbook, against a running API and worker: nothing sends inside the request; parent results stay hidden until publish; a bad phone does not abort email; bulk WhatsApp stays spaced; admin list and resend work.
- [ ] `run-phase5.sh` end to end, after the Bruno admin user exists on `testacademy`.
- [x] A local Celery worker moved `invoice_generated` and `payment_confirmed` from `queued` to `sent` on the console email backend (2026-11-06 walk). WhatsApp for that parent was not expected to send: redeeming a linking code creates a guardian with a blank phone. SMTP and Cloud API are still unconfirmed. The worker is not running now.
- [ ] Meta approval of the three templates.
- [ ] Paystack: live test-card checkout, and platform commission in `PlatformTransactionLog` matching the Paystack dashboard. Tests and Bruno use the stub gateway and a fixture HMAC secret.
- [ ] Two-schema isolation and “no secrets committed” were not re-audited on 2026-11-06.
- [ ] Login bug, already reproduced: a leftover platform `refresh_token` (`tenant_schema: public`) is applied before `X-Tenant-Slug`, so school login returns `no_membership` even when the admin membership exists. Clear the cookie for `localhost:8000`, or fix the middleware so a public refresh cookie does not pin a school login.
- [x] Gap-closure live smoke on `testacademy` (memberships, guardians/regenerate, payment ledger empty-state + 403/405 paths, `/auth/me`, assessment set-scheme/clone-scheme). Those modules now run under `python -m pytest` on SQLite (full suite **296 passed** on 2026-11-11).
- [ ] School-wide fees, all-class generate, and combined Paystack checkout on a live `testacademy` walk (bursar onboard, one charge for two invoices, generate with no `class_level`). Covered by pytest; not yet clicked through in the browser. The open browser session on 2026-11-11 was not a bursar, so `/bursar/invoices/generate` did not render the form.

## Not in this API

- Creating or editing a school over HTTP. `GET /api/platform/tenants/` is read-only. Schools are still created with `create_test_tenant`.
- Replaying a Paystack webhook. `GET /api/platform/webhooks/` is a read of `WebhookLog`. `POST /api/webhooks/paystack/` is unchanged.
- A score-entry pending dashboard. Attendance overview reports register status. There is no “which subjects still have no scores” route.
- Phase 6+ product work (not written).
