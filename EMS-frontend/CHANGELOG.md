# EMS-frontend changelog

Status snapshot as of **2026-11-06** (later the same day: publish screen, linking codes, teacher grids, bursar invoice list, platform tenants and webhooks). This is the current state of the Next.js monorepo, not a release history. The school UI is wired through the Phase 5 publish gate. There is still no notifications screen.

Apps: `apps/tenant` (`http://{slug}.localhost:3000`) and `apps/platform` (`http://platform.localhost:3001`). API host is `http://localhost:8000`. School calls send `X-Tenant-Slug`. The platform app omits it. Contract: `docs/API_MAPPING.md`, `docs/INTEGRATION.md`.

## Current state

| Area | State |
|---|---|
| Shell | Next.js App Router, Tailwind v4, Paper Brutalism. Shared UI includes Button, Card, Badge, Input, Label, KpiCard, EmptyState |
| Auth | Live login, 2FA verify/enroll, invite accept, parent signup, linking-code redeem. Mocks remain behind `NEXT_PUBLIC_USE_MOCKS` |
| Academics | Admin screens call `lib/api/academics` (sessions, terms, classes, students, enrollment, assignments) |
| Assessment | Teacher mark grid, components, broadsheet, remarks, and admin publish call `lib/api/assessment`. Parent results and PDF download call the API. The PDF request sends `Accept: */*` because `application/pdf` is a 406 |
| Attendance | Teacher register is a status grid. Admin overview and parent attendance call `lib/api/attendance` |
| Finance | Bursar fee structures, invoice list, generate, payment account, manual payment (invoice picker), and parent invoices/pay call `lib/api/finance` |
| Platform | Login, revenue, `GET /api/platform/tenants/`, and `GET /api/platform/webhooks/` are live. The client still omits `X-Tenant-Slug` |

There is no `lib/api` client for `/api/communications/`. `assessmentApi.publish` posts `{ class_level, arm, term }`.

## Wired routes

School app, live API unless noted:

- Auth: `/login`, `/2fa/verify`, `/2fa/setup`, `/2fa/enroll`, `/accept-invite`, `/parents/signup`, `/link-student`
- Admin: `/admin`, `/admin/academics`, `/admin/students` (unused `linking_code` is shown and copyable; a used code reads “Used”), `/admin/enrollment`, `/admin/assignments`, `/admin/results` (publish), `/admin/attendance`, `/admin/fees`
- Admin staff (`/admin/staff`): invite create only. The directory says there is no staff-list API
- Teacher: `/teacher`, `/teacher/marks` (one row per student and component; blank cells are omitted), `/teacher/components` (scheme is still a JSON post, and the API requires a school admin), `/teacher/broadsheet`, `/teacher/attendance` (present / absent / late / excused; an unset row is not sent), `/teacher/remarks`
- Bursar: `/bursar`, `/bursar/fee-structures`, `/bursar/invoices` (table from `GET /api/finance/invoices/`), `/bursar/invoices/generate`, `/bursar/payment-account`, `/bursar/payments`, `/bursar/payments/manual` (invoice `<select>`, not a pasted UUID)
- Parent: `/parent`, `/parent/students`, `/parent/results`, `/parent/attendance`, `/parent/fees`, `/parent/fees/pay`, `/parent/fees/result`

Platform app:

- `/login`, the revenue home, `/tenants`, and `/webhooks` call the platform API
- Tenants lists schools. Webhooks lists deliveries and shows “No deliveries yet” when `results` is empty. Neither page creates a school or replays a webhook

A browser walk on `http://testacademy.localhost:3000` the same day used the linking code `RAUEPZMX`, published from `/admin/results`, downloaded the PDF, selected Ada Okonkwo’s invoice, recorded ₦50,000 cash (`CASH-001`), and showed the parent fees page as paid with balance ₦0.00. Class-subject assignment, class-teacher assignment, the assessment scheme, and the ₦50,000 fee structure were created with the admin API because those screens do not collect the fields the API requires.

## Needs doing

- **Notification log.** Admin list/filter of `GET /api/communications/notifications/` and resend via `POST /api/communications/notifications/{id}/resend/` (failed rows only). No screen exists for this.
- **Assignment editors.** `/admin/assignments` lists class-subject and class-teacher rows. It does not create them.
- **Assessment scheme.** `/teacher/components` still posts raw JSON, and the endpoint requires a school admin.
- **Fee structure form.** The bursar form sends a name. Amount, class, and term were set through the API during the walk.
- **Staff top bar.** It always shows `2025/2026 · First Term` from `lib/mocks/staff-nav.ts`, including when mocks are off.
- **Parent results empty state.** Before publish, say the term is not published yet instead of dumping the JSON body. PDF download should expect 404 until then.

## Needs confirming

- [x] School login on `testacademy.localhost:3000` for admin, teacher, bursar, and parent (2026-11-06 walk). Admin and bursar completed TOTP. This browser did not hit the public `refresh_token` / `no_membership` bug.
- [ ] A leftover platform `refresh_token` cookie on `localhost:8000` still makes a later login return `no_membership`. The platform login in the Cursor browser hit this with an existing school session. Clear the cookie for `localhost:8000` before switching between school and platform. The middleware is not fixed.
- [ ] Local refresh: `*.localhost:3000` → `localhost:8000` is cross-site. Refresh only works when the API sets `LOCAL_CROSS_SITE_COOKIES` (SameSite=None). Confirm whether the cookie is actually sent.
- [x] Clicked on `testacademy`: linking code on the students page, teacher mark grid, attendance register, `/admin/results` publish, parent results, report-card PDF, invoice list, manual cash via the invoice picker, parent balance ₦0.00.
- [x] Platform tenants and webhooks on `platform.localhost:3001` with no `X-Tenant-Slug`. Tenants showed Test Academy. Webhooks showed the empty state. Revenue was not re-clicked in that pass.
- [ ] `NEXT_PUBLIC_USE_MOCKS` stays off for any check that should hit Django. The staff top bar still reads a mock term label.

## Not in this frontend

- WhatsApp or email sending (API and Celery). The walk’s invoice and payment emails were printed by the API worker.
- Paystack webhook handling (Django `POST /api/webhooks/paystack/` only). The platform page lists logs; it does not accept deliveries.
- Creating schools. `GET /api/platform/tenants/` is read-only. Schools still come from `create_test_tenant`.
- A staff directory. Invites are create-only because the API has no membership list.
