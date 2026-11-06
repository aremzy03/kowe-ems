# EMS-frontend changelog

Status snapshot as of **2026-11-06**. This is the current state of the Next.js monorepo, not a release history. The school UI is wired to the Phase 0–4 API. Phase 5 (notifications and the result publish gate) exists on the API only.

Apps: `apps/tenant` (`http://{slug}.localhost:3000`) and `apps/platform` (`http://platform.localhost:3001`). API host is `http://localhost:8000`. School calls send `X-Tenant-Slug`. The platform app omits it. Contract: `docs/API_MAPPING.md`, `docs/INTEGRATION.md`.

## Current state

| Area | State |
|---|---|
| Shell | Next.js App Router, Tailwind v4, Paper Brutalism. Shared UI includes Button, Card, Badge, Input, Label, KpiCard, EmptyState |
| Auth | Live login, 2FA verify/enroll, invite accept, parent signup, linking-code redeem. Mocks remain behind `NEXT_PUBLIC_USE_MOCKS` |
| Academics | Admin screens call `lib/api/academics` (sessions, terms, classes, students, enrollment, assignments) |
| Assessment | Teacher marks, components, broadsheet, remarks call `lib/api/assessment`. Parent results and PDF download call the API |
| Attendance | Teacher register and admin overview call `lib/api/attendance`. Parent attendance calls the API |
| Finance | Bursar fee structures, invoices, payment account, manual payments, and parent invoices/pay call `lib/api/finance` |
| Platform | Login and `GET /api/platform/revenue/` are live. Tenants and webhooks are intentional empty states |

There is no `lib/api` client for `/api/communications/` or `POST /api/assessment/results/publish/`.

## Wired routes

School app, live API unless noted:

- Auth: `/login`, `/2fa/verify`, `/2fa/setup`, `/2fa/enroll`, `/accept-invite`, `/parents/signup`, `/link-student`
- Admin: `/admin`, `/admin/academics`, `/admin/students`, `/admin/enrollment`, `/admin/assignments`, `/admin/attendance`, `/admin/fees`
- Admin staff (`/admin/staff`): invite create only. The directory says there is no staff-list API
- Teacher: `/teacher`, `/teacher/marks`, `/teacher/components`, `/teacher/broadsheet`, `/teacher/attendance`, `/teacher/remarks`
- Bursar: `/bursar`, `/bursar/fee-structures`, `/bursar/invoices`, `/bursar/invoices/generate`, `/bursar/payment-account`, `/bursar/payments`, `/bursar/payments/manual`
- Parent: `/parent`, `/parent/students`, `/parent/results`, `/parent/attendance`, `/parent/fees`, `/parent/fees/pay`, `/parent/fees/result`

Platform app:

- `/login` and the revenue home are live
- `/tenants` and `/webhooks` render empty states. The API does not expose tenant provisioning or a webhook admin list

## Needs doing

- **Publish control.** An admin screen that calls `POST /api/assessment/results/publish/` with `class_level`, `arm`, and `term`. Until that exists, parents stay on unpublished results unless someone calls the API directly.
- **Parent results empty state.** `/parent/results` dumps the JSON body. Before publish the API returns 200 with `summary: null` and `subject_results: []`. The page should say results are not published yet, and PDF download should expect 404 until then.
- **Notification log.** Admin list/filter of `GET /api/communications/notifications/` and resend via `POST /api/communications/notifications/{id}/resend/` (failed rows only). No route exists for this.
- **API mapping.** `docs/API_MAPPING.md` and `docs/INTEGRATION.md` stop at Phases 0–4. Add publish and communications when those screens exist.

## Needs confirming

- [ ] School login and 2FA on a real tenant host (`testacademy2.localhost` has an admin; `testacademy` had no memberships when last checked). Network must show `X-Tenant-Slug` and the API host `localhost:8000`.
- [ ] A leftover platform `refresh_token` cookie on `localhost:8000` makes school login return `no_membership`. Confirm a clean login after that cookie is cleared.
- [ ] Local refresh: `*.localhost:3000` → `localhost:8000` is cross-site. Refresh only works when the API sets `LOCAL_CROSS_SITE_COOKIES` (SameSite=None). Confirm whether the cookie is actually sent.
- [ ] Role paths already wired: academics CRUD, mark entry, broadsheet, attendance register, fee structure, invoice generate, parent pay, manual cash. These were not re-clicked on 2026-11-06.
- [ ] Platform revenue on `platform.localhost:3001` with no `X-Tenant-Slug`.
- [ ] `NEXT_PUBLIC_USE_MOCKS` is off for any check that should hit Django.

## Not in this frontend

- WhatsApp or email sending (API and Celery).
- Paystack webhook handling (Django only).
- Creating schools (API management command `create_test_tenant`).
- A staff directory, a bursar invoice browser, or a platform tenant list, because those APIs do not exist.
