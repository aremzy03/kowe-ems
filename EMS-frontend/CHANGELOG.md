# EMS-frontend changelog

Status snapshot as of **2026-11-06** (evening: staff directory, guardians/linking codes, payment ledger, `/me` shell, academics U/D, assessment scheme, notifications, platform 2FA). This is the current state of the Next.js monorepo, not a release history. The school UI is wired through the Phase 5 publish gate and the same-day API gap-closure endpoints.

Apps: `apps/tenant` (`http://{slug}.localhost:3000`) and `apps/platform` (`http://platform.localhost:3001`). API host is `http://localhost:8000`. School calls send `X-Tenant-Slug`. The platform app omits it. Contract: `docs/API_MAPPING.md`, `docs/INTEGRATION.md`.

## Current state

| Area | State |
|---|---|
| Shell | Next.js App Router, Tailwind v4, Paper Brutalism. Shared UI includes Button, Card, Badge, Input, Label, KpiCard, EmptyState, ConfirmDeleteModal |
| Auth | Live login, 2FA verify/enroll, invite accept, parent signup, linking-code redeem, `GET /api/auth/me/` for display name + school name. Mocks remain behind `NEXT_PUBLIC_USE_MOCKS` |
| Academics | Admin screens call `lib/api/academics` with list/create/**update/delete** for sessions, terms, class levels, arms, subjects, students, enrollments. Guardians and guardian-links on the students page. Linking-code copy + reissue |
| Memberships | `lib/api/memberships.ts`. `/admin/staff` lists members, role/active PATCH, soft deactivate, pending invites + revoke |
| Assessment | Teacher mark grid, components (assignment picker), broadsheet, remarks, admin publish, **admin assessment scheme** (`/admin/components`: set-scheme / clone-scheme / edit / delete). Parent results and PDF download call the API. The PDF request sends `Accept: */*` because `application/pdf` is a 406 |
| Attendance | Teacher register is a status grid. Admin overview and parent attendance call `lib/api/attendance` |
| Finance | Fee structures L/C/U/D, invoice list + **detail with nested payments**, generate, payment account, **payment ledger**, manual payment (invoice picker), parent invoices/pay with nested payments |
| Communications | `lib/api/communications.ts`. `/admin/notifications` lists/filters delivery logs and resends failed rows (school admin only) |
| Platform | Login with 2FA challenge routing, revenue, tenants list, webhooks list. Client still omits `X-Tenant-Slug`. `/me` populates the operator name in the shell |

## Gap closure (2026-11-06 evening)

Tenant and platform UI for the API endpoints added the same evening. Verified on `testacademy.localhost:3000` / `platform.localhost:3001` where noted in the agent walks.

### Staff and memberships

- **`/admin/staff`** uses `GET /api/memberships/members/` (real directory) and `GET/DELETE /api/memberships/invites/`. Role select, deactivate/reactivate, invite create, pending-invite revoke. In-memory “recent invites” and the “no staff-list API” copy are gone.
- New client: `apps/tenant/src/lib/api/memberships.ts`.

### Students / guardians / linking codes

- Students page: **Guardians** panel (edit contact, add & link, link existing, set primary, unlink), **Reissue** linking code via `POST …/students/{id}/regenerate-linking-code/`, plus student **edit** modal and confirmed **delete** (409 if billed).
- `academicsApi` extended for guardians, guardian-links, regenerate, student update/remove.

### Finance ledger

- **`/bursar/invoices/[id]`** — invoice detail with line items + nested payments. List rows link to View.
- **`/bursar/payments`** is a real ledger (`GET /api/finance/payments/` with status/term filters), not a second collections dashboard. Collections stay on `/bursar`.
- Parent fees show nested payment rows when present.
- `financeApi`: `getInvoice`, `listPayments`, `getPayment`, fee-structure update/remove.

### Auth shell (`/me`)

- Tenant `authApi.me()`; auth provider hydrates after login/refresh; `use-app-session` live mode uses real `displayName` and `schoolName` (no more hardcoded `"School"` / `"Bursar · Bursar"`).
- Platform shell uses the same endpoint (no tenant header) for the operator name.
- Login / 2FA success may carry nested `me`; refetch remains source of truth.

### Academics and fee U/D

- **`/admin/academics`**: inline edit; sessions/terms activate/deactivate via PATCH `is_active`; confirmed delete (409 via protected destroy).
- **`/admin/enrollment`**: status select (`active` / `withdrawn` / `graduated`) + confirmed delete.
- **Fee structures** panel: edit modal + confirmed delete (409 if on invoices).
- Shared `ConfirmDeleteModal`.

### Assessment scheme

- **`/admin/components`** (nav: Assessment scheme): pick class/subject/term (or from assignment), view weights, **Save scheme** (`set-scheme`), **Clone** onto another subject/term, PATCH/DELETE single components with the 100% weight rule surfaced in errors.
- Teacher `/teacher/components` picks among assignments instead of only the first.

### Notifications

- **`/admin/notifications`** (admin nav only): filters for status / channel / trigger / date range; Resend on failed rows only. Bursar excluded (API is school-admin only).

### Platform 2FA

- Login handles `requires_2fa` + `pre_auth_token` → `/2fa/verify` or `/2fa/setup` (`/2fa/enroll` aliases setup). Password-only success unchanged.
- Live API may still return tokens immediately for platform operators until `REQUIRE_ADMIN_2FA` / role gating includes `platform_admin`. Pages match the tenant contract.

## Wired routes

School app, live API unless noted:

- Auth: `/login`, `/2fa/verify`, `/2fa/setup`, `/2fa/enroll`, `/accept-invite`, `/parents/signup`, `/link-student`
- Admin: `/admin`, `/admin/academics`, `/admin/students`, `/admin/enrollment`, `/admin/assignments` (list only; create still deferred), `/admin/components` (scheme), `/admin/results` (publish), `/admin/notifications`, `/admin/attendance`, `/admin/fees`, `/admin/staff` (directory + invites)
- Teacher: `/teacher`, `/teacher/marks`, `/teacher/components` (assignment picker; scheme is admin-written), `/teacher/broadsheet`, `/teacher/attendance`, `/teacher/remarks`
- Bursar: `/bursar`, `/bursar/fee-structures`, `/bursar/invoices`, `/bursar/invoices/[id]`, `/bursar/invoices/generate`, `/bursar/payment-account`, `/bursar/payments` (ledger), `/bursar/payments/manual`
- Parent: `/parent`, `/parent/students`, `/parent/results`, `/parent/attendance`, `/parent/fees`, `/parent/fees/pay`, `/parent/fees/result`

Platform app:

- `/login`, `/2fa/verify`, `/2fa/setup`, `/2fa/enroll`, revenue home, `/tenants`, `/webhooks`
- Tenants lists schools. Webhooks lists deliveries. Neither page creates a school or replays a webhook

## Needs doing

- **Assignment create UI.** `/admin/assignments` lists class-subject and class-teacher rows. Create is still deferred. Staff picker API is ready: `GET /api/memberships/members/?role=teacher&is_active=true` → use `user` UUID as `teacher`.
- **Staff top bar term label.** Confirm it follows the active session/term from the API (earlier it could show a mock label when mocks were off).
- **Parent results empty state.** Before publish, say the term is not published yet instead of dumping the JSON body. PDF download should expect 404 until then.
- **Platform 2FA live challenge.** Frontend is ready; enable when backend gates `platform_admin` (or turn on `REQUIRE_ADMIN_2FA` for that role).

## Needs confirming

- [x] School login on `testacademy.localhost:3000` for admin, teacher, bursar, and parent (2026-11-06 walk). Admin and bursar completed TOTP. This browser did not hit the public `refresh_token` / `no_membership` bug.
- [ ] A leftover platform `refresh_token` cookie on `localhost:8000` still makes a later login return `no_membership`. Clear the cookie for `localhost:8000` before switching between school and platform. The middleware is not fixed.
- [ ] Local refresh: `*.localhost:3000` → `localhost:8000` is cross-site. Refresh only works when the API sets `LOCAL_CROSS_SITE_COOKIES` (SameSite=None). Confirm whether the cookie is actually sent.
- [x] Clicked on `testacademy` (day walk): linking code on the students page, teacher mark grid, attendance register, `/admin/results` publish, parent results, report-card PDF, invoice list, manual cash via the invoice picker, parent balance ₦0.00.
- [x] Platform tenants and webhooks on `platform.localhost:3001` with no `X-Tenant-Slug`.
- [x] Evening gap-closure walks: staff directory/invites, guardians + reissue, payment ledger/invoice detail, `/me` school name, academics/enrollment/fee U/D, assessment set-scheme/clone, notifications list/resend, platform login password-only + 2FA page shells.
- [ ] `NEXT_PUBLIC_USE_MOCKS` stays off for any check that should hit Django.

## Not in this frontend

- WhatsApp or email sending (API and Celery). The walk’s invoice and payment emails were printed by the API worker.
- Paystack webhook handling (Django `POST /api/webhooks/paystack/` only). The platform page lists logs; it does not accept deliveries.
- Creating schools. `GET /api/platform/tenants/` is read-only. Schools still come from `create_test_tenant`.
- Assignment create forms (list-only until the create UI lands).
- Broadcast / compose notifications (delivery log + resend only).
