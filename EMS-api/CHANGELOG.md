# EMS-api changelog

Status snapshot as of **2026-11-06** (later the same day: staff invoice list, platform directory reads, Django admin). This is the current state of the Django API, not a release history. Phases 0–5 are implemented in code. Several exit checks are still manual or live-only.

Playbooks: `EMS-Phase0-Init-Playbook.md` through `EMS-Phase5-Init-Playbook.md`. Bruno collection: `bruno/` (Phases 0–5).

## Current state

Schema-per-tenant (`django-tenants`). One API host. The school schema comes from the JWT `tenant_schema` claim, then `X-Tenant-Slug`. `Host` does not select a tenant (Option B / Phase 0.1).

Local settings: `config.settings.local`. Postgres for this machine is the `ems-api_db_1` container on host port **5433**. Redis is already on **6379**. `manage.py test` cannot `CREATE DATABASE` (`dev_user` lacks `CREATEDB`); suites were run with `--keepdb` against the existing database.

Local schools present: `testacademy`, `testacademy2`. `testacademy` now has an active admin (`admin@testacademy.local`) plus a teacher, bursar, and parent created during the browser walk. `testacademy2` still has `admin@testacademy2.local`.

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

## Phase 5 (2026-11-06)

- **NotificationLog** (tenant schema): recipient, channel `email` / `whatsapp`, trigger `invoice_generated` / `payment_confirmed` / `result_published`, status `queued` / `sent` / `failed`.
- **Celery** app `ems`, `docker-compose` worker, task `send_notification(notification_log_id, schema_name)`. Eager mode is off. Transient failures retry (3 attempts). Permanent failures fail immediately.
- **Email** queues on the task. Local backend is console. Production is generic SMTP env vars. Result mail links to `/parent/results` and does not include scores.
- **WhatsApp** queues on the same task. Local `WHATSAPP_BACKEND=console`. Production calls the Cloud API with `requests` (no BSP SDK). Bulk sends are spaced 6 seconds apart. A bad number fails that log only.
- **Publish gate.** `TermResultSummary.is_published` defaults to false. `POST /api/assessment/results/publish/` (school admin with confirmed TOTP). Until publish, a parent’s results payload is empty and the report-card PDF is 404. Staff can still read unpublished results. Publish queues email and WhatsApp once, on commit.
- **Signals.** A new invoice, and a payment whose status becomes `success`, queue email after commit. WhatsApp is included when `Guardian.phone_number` is non-blank. A later save does not send again. Result alerts are not sent from these signals.
- **Admin API.** `GET /api/communications/notifications/` and `POST /api/communications/notifications/{id}/resend/`. Resend is only for `failed`, and it re-queues the same row.

Tests recorded during the build: communications 66 passed after the admin API; finance + communications + publication **169 passed** after the signals. Bruno parsed the 14 new `bruno/Communications/` requests.

## Same-day additions (2026-11-06, after Phase 5)

- **Staff invoices.** `GET /api/finance/invoices/` for admin or bursar. Optional `?term=` and `?class_level=`. Response is `{ count, results }` using `InvoiceSerializer`. Parent `my-invoices/` is unchanged. `finance.tests.StaffInvoiceListTests`: 4 passed (`--keepdb`).
- **Platform directory reads.** `GET /api/platform/tenants/` (schools only; the public-schema row is omitted) and `GET /api/platform/webhooks/` (newest 100 `WebhookLog` rows; `error_message` clipped to 280 characters, `payload_preview` to 200; raw `payload` is not returned). Both are `IsPlatformAdmin` and stay on the public schema. They do not provision a school or replay a delivery. `platform_admin.tests.PlatformDirectoryListTests`: 3 passed (`--keepdb`). Revenue and `POST /api/webhooks/paystack/` are unchanged.
- **Term reads.** `GET /api/academics/terms/` list and retrieve are any active school member. Writes stay admin-only. Class level, arm, and subject list/retrieve stay admin or teacher.
- **Django admin.** `http://127.0.0.1:8000/admin/` was already mounted. `/admin` and `/admin/` are public-path prefixes, so they do not 400 for a missing `X-Tenant-Slug`. Public-schema requests set `request.tenant` to the public `Tenant` row, or to django-tenants’ `FakeTenant` when that row is missing, because the admin index calls `is_public_schema` and crashes on `None`. Every concrete model in accounts, platform_admin, memberships, academics, assessment, attendance, finance (including `InvoiceLineItem`), communications, and `otp_totp.TOTPDevice` is registered. Secrets stay off the changelist. School-schema rows resolve only when the connection is that tenant. Login requires `is_staff`; a school admin is not enough. `platform_admin.test_tenant_resolution`: 22 passed (`--keepdb`) after the tenant bind. `manage.py check`: no issues.

A browser walk on `testacademy` the same day published JSS1 A (1st term, 2026/2027), downloaded the report-card PDF (200, 15,680 bytes), and recorded a ₦50,000 cash payment. A Celery worker moved `invoice_generated` and `payment_confirmed` email rows to **sent** (console backend). Publish did not queue a notification because it ran before the parent account existed. The worker was shut down afterward; it is not left running.

## Needs doing

- Submit the three Utility templates in WhatsApp Manager before live Cloud API sends: `kowe_invoice_generated`, `kowe_payment_confirmed`, `kowe_result_published` (`communications/whatsapp_templates.py`).
- Set production `EMAIL_*` and `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` when those channels go live.
- Run a Celery worker in any environment where rows should leave `queued`.
- Point `bruno/.env` at the `testacademy` admin (`admin@testacademy.local` plus that user’s TOTP secret) and rerun `bruno/scripts/run-phase5.sh`. The earlier live run stopped at login with **401** when the schema had no memberships. That membership now exists. The Bruno suite has not been rerun.
- Update `bruno/Assessment/20` so `run-phase2.sh` does not expect a parent PDF with HTTP 200 before publish. Phase 5 covers that PDF in `Communications/07` (404) and `Communications/10` (200).

## Needs confirming

- [ ] Phase 5 exit list in the playbook, against a running API and worker: nothing sends inside the request; parent results stay hidden until publish; a bad phone does not abort email; bulk WhatsApp stays spaced; admin list and resend work.
- [ ] `run-phase5.sh` end to end, after the Bruno admin user exists on `testacademy`.
- [x] A local Celery worker moved `invoice_generated` and `payment_confirmed` from `queued` to `sent` on the console email backend (2026-11-06 walk). WhatsApp for that parent was not expected to send: redeeming a linking code creates a guardian with a blank phone. SMTP and Cloud API are still unconfirmed. The worker is not running now.
- [ ] Meta approval of the three templates.
- [ ] Paystack: live test-card checkout, and platform commission in `PlatformTransactionLog` matching the Paystack dashboard. Tests and Bruno use the stub gateway and a fixture HMAC secret.
- [ ] Two-schema isolation and “no secrets committed” were not re-audited on 2026-11-06.
- [ ] Login bug, already reproduced: a leftover platform `refresh_token` (`tenant_schema: public`) is applied before `X-Tenant-Slug`, so school login returns `no_membership` even when the admin membership exists. Clear the cookie for `localhost:8000`, or fix the middleware so a public refresh cookie does not pin a school login.

## Not in this API

- Creating or editing a school over HTTP. `GET /api/platform/tenants/` is read-only. Schools are still created with `create_test_tenant`.
- Replaying a Paystack webhook. `GET /api/platform/webhooks/` is a read of `WebhookLog`. `POST /api/webhooks/paystack/` is unchanged.
- A staff membership list. Invites are create/accept only.
- A score-entry pending dashboard. Attendance overview reports register status. There is no “which subjects still have no scores” route.
- Phase 6+ product work (not written).
