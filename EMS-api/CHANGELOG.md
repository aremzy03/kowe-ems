# EMS-api changelog

Status snapshot as of **2026-11-06**. This is the current state of the Django API, not a release history. Phases 0–5 are implemented in code. Several exit checks are still manual or live-only.

Playbooks: `EMS-Phase0-Init-Playbook.md` through `EMS-Phase5-Init-Playbook.md`. Bruno collection: `bruno/` (Phases 0–5).

## Current state

Schema-per-tenant (`django-tenants`). One API host. The school schema comes from the JWT `tenant_schema` claim, then `X-Tenant-Slug`. `Host` does not select a tenant (Option B / Phase 0.1).

Local settings: `config.settings.local`. Postgres follows `.env` (this machine used port **5432**). `manage.py test` cannot `CREATE DATABASE` (`dev_user` lacks `CREATEDB`); suites were run with Django’s runner against the existing dev database.

Local schools present: `testacademy`, `testacademy2`.

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

## Needs doing

- Submit the three Utility templates in WhatsApp Manager before live Cloud API sends: `kowe_invoice_generated`, `kowe_payment_confirmed`, `kowe_result_published` (`communications/whatsapp_templates.py`).
- Set production `EMAIL_*` and `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` when those channels go live.
- Run a Celery worker in any environment where rows should leave `queued`.
- Point `bruno/.env` at a real `testacademy` admin (`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_TOTP_SECRET`) and rerun `bruno/scripts/run-phase5.sh`. The last live run stopped at login with **401**. Schema `testacademy` had **no** `SchoolMembership` rows. `testacademy2` does have an active admin (`admin@testacademy2.local`).
- Update `bruno/Assessment/20` so `run-phase2.sh` does not expect a parent PDF with HTTP 200 before publish. Phase 5 covers that PDF in `Communications/07` (404) and `Communications/10` (200).

## Needs confirming

- [ ] Phase 5 exit list in the playbook, against a running API and worker: nothing sends inside the request; parent results stay hidden until publish; a bad phone does not abort email; bulk WhatsApp stays spaced; admin list and resend work.
- [ ] `run-phase5.sh` end to end, after the Bruno admin user exists on `testacademy`.
- [ ] A Celery worker actually moving logs from `queued` to `sent` (console email / console WhatsApp locally, SMTP and Cloud API in production).
- [ ] Meta approval of the three templates.
- [ ] Paystack: live test-card checkout, and platform commission in `PlatformTransactionLog` matching the Paystack dashboard. Tests and Bruno use the stub gateway and a fixture HMAC secret.
- [ ] Two-schema isolation and “no secrets committed” were not re-audited on 2026-11-06.
- [ ] Login bug, already reproduced: a leftover platform `refresh_token` (`tenant_schema: public`) is applied before `X-Tenant-Slug`, so school login returns `no_membership` even when the admin membership exists. Clear the cookie for `localhost:8000`, or fix the middleware so a public refresh cookie does not pin a school login.

## Not in this API

- Tenant provisioning and a webhook admin list. Platform HTTP API is `GET /api/platform/revenue/` plus `POST /api/webhooks/paystack/`. Schools are created with `create_test_tenant`.
- A staff membership list. Invites are create/accept only.
- A bursar invoice list. Invoice generation and parent `my-invoices/` exist.
- Phase 6+ product work (not written).
