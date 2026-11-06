# EMS Frontend ↔ API Mapping

Maps UI shell routes in **EMS-frontend** (tenant school UI) to EMS-api endpoints. Clients are implemented from prompt 01 onward — this document is the contract only.

**Sibling apps**

| App | Path | Host (local) | API scope |
|---|---|---|---|
| Tenant school UI | `EMS-frontend/` (this repo) | `{slug}.localhost:3000` | `scope: 'tenant'` → send `X-Tenant-Slug` |
| Platform admin UI | `apps/platform` (`@ems/platform`) | `platform.localhost:3001` | `scope: 'platform'` → **omit** `X-Tenant-Slug` |

Platform UI must **not** live under EMS-frontend `/platform`. Landing links should point at the platform host absolute URL.

---

## Tenant contract

### Header

| Rule | Detail |
|---|---|
| Name | `X-Tenant-Slug` |
| Value | First hostname label only (`testacademy` from `testacademy.localhost`) |
| Source | Frontend hostname — client: `window.location.hostname`; server/RSC: incoming `Host` / middleware-forwarded slug. **Never** from the API URL. **Never** in the query string. |
| Attach | Every `scope: 'tenant'` call (school auth including login, 2FA, refresh, logout; memberships; academics; assessment; attendance; finance) — pre-auth and post-auth |
| Omit | `scope: 'platform'` (platform login, `/api/platform/*`). Paystack webhooks are Django-only |
| Fail closed | If tenant scope and slug cannot be derived → throw in the client; do not send a headerless school request |

### API host

- One fixed base: `NEXT_PUBLIC_TENANT_API_URL` (e.g. `http://localhost:8000`). Same for every school.
- Do **not** call `testacademy.localhost:8000` as the API base. Host on the API does not select a schema.

### Server resolution (Django HeaderTenantMiddleware)

1. Valid JWT (Bearer **or** refresh cookie) → claim `tenant_schema`. Missing/unknown → **401** `Invalid tenant claim in token.` Claim `public` stays public. JWT wins; mismatched header is ignored. Expired JWT → fall through.
2. Else `X-Tenant-Slug` → Domain/schema lookup. Unknown/inactive → **400** `Unknown tenant.`
3. Else → **400** `Tenant identification required`, except OPTIONS and public-path prefixes `/api/auth/`, `/api/platform/`, `/api/webhooks/` (public only when no JWT/header).

### Auth exemption caveat

`/api/auth/` staying public without JWT/header is for **platform** login. School login/2FA/refresh/logout **must** still send `X-Tenant-Slug`. Without it, school login runs on public schema and **401**s (no school membership) — not a 400.

`POST /api/memberships/invites/accept/` and `POST /api/memberships/parents/signup/` are **not** under the exemption; missing header → 400.

### Cookies / CSRF (local caveat)

| Piece | Behavior |
|---|---|
| Access token | JWT in JSON → memory (optional short persistence); `Authorization: Bearer`. Claims include `tenant_schema` (+ often `role`). |
| Refresh token | httpOnly cookie `refresh_token` on API host, path `/api/auth/`, SameSite=Strict. JS never reads it. |
| CSRF | `X-CSRFToken` matching `csrftoken` on `POST /api/auth/refresh/` and `POST /api/auth/logout/` |
| Credentials | `credentials: 'include'` so the API-host refresh cookie *can* be sent |
| Production | `schoola.yourapp.com` → `api.yourapp.com` is same-site; Strict cookie is sent |
| **Local** | `testacademy.localhost:3000` → `localhost:8000` is **cross-site** (localhost is a public suffix). Strict refresh cookie **will not** be sent. Host-only `csrftoken` is not readable via `document.cookie` from `*.localhost`. Do not invent CSRF/cookie JSON endpoints. |

### Env (tenant app)

```
NEXT_PUBLIC_TENANT_API_URL=http://localhost:8000
NEXT_PUBLIC_PLATFORM_API_URL=http://localhost:8000
NEXT_PUBLIC_ROOT_DOMAIN=localhost
NEXT_PUBLIC_PLATFORM_HOST=platform.localhost
```

`getTenantSlug` returns `null` for `ROOT_DOMAIN` itself and for `PLATFORM_HOST`.

### Invite path

Django emails `{TENANT_FRONTEND_ORIGIN_TEMPLATE}/accept-invite?token=` (local default `http://{slug}.localhost:3000/accept-invite?token=`). UI shell mock route is `/invite/accept` — implement or rewrite to `/accept-invite` to match emails. Tenant comes from hostname, not the token.

---

## Auth & memberships

| UI route | Method | Path | Scope | Notes |
|---|---|---|---|---|
| `/login` | POST | `/api/auth/login/` | tenant | Body: `{ email, password }`. Success: `{ access, role, requires_2fa }` or `{ requires_2fa, pre_auth_token, role, enrollment_required? }` |
| `/2fa/verify` | POST | `/api/auth/2fa/verify/` | tenant | `{ pre_auth_token, totp_code }` → access + refresh cookie |
| `/2fa/enroll`, `/2fa/setup` | POST | `/api/auth/2fa/enroll/` | tenant | Auth: pre_auth Bearer. Returns `{ secret, config_url, qr_code }` |
| `/2fa/enroll` (confirm) | POST | `/api/auth/2fa/enroll/confirm/` | tenant | Confirm TOTP; may issue full tokens |
| (client refresh) | POST | `/api/auth/refresh/` | tenant | Cookie + CSRF; returns new `access` |
| (logout) | POST | `/api/auth/logout/` | tenant | Cookie + CSRF |
| `/dev/api-ping` | POST | `/api/auth/verify/` | tenant | Body `{ token }`; ping with header visible |
| `/accept-invite` (was `/invite/accept`) | POST | `/api/memberships/invites/accept/` | tenant | `{ token, password, first_name, last_name }` — header required |
| `/parents/signup` | POST | `/api/memberships/parents/signup/` | tenant | Header required |
| `/admin/staff` (invite) | POST | `/api/memberships/invites/` | tenant | Auth admin; `{ email, role }` |
| `/link-student` | POST | `/api/academics/linking-codes/redeem/` | tenant | Parent redeem linking code |

No `/me` endpoint for MVP — role comes from login/2FA JSON (and optional client persistence).

---

## Admin

| UI route | Method | Path | Notes |
|---|---|---|---|
| `/admin` | GET | `/api/finance/dashboard/collections/?term=` | Collections KPI (shared with bursar) |
| `/admin` | GET | `/api/attendance/admin/overview/?date=` or `?term=` | Attendance overview |
| `/admin/academics` | CRUD | `/api/academics/sessions/` | ViewSet |
| | CRUD | `/api/academics/terms/` | ViewSet; PATCH term for `total_school_days` |
| | CRUD | `/api/academics/class-levels/` | ViewSet |
| | CRUD | `/api/academics/arms/` | ViewSet |
| | CRUD | `/api/academics/subjects/` | ViewSet |
| `/admin/students` | CRUD | `/api/academics/students/` | ViewSet |
| `/admin/enrollment` | CRUD | `/api/academics/enrollments/` | ViewSet |
| `/admin/assignments` | CRUD | `/api/academics/class-subject-assignments/` | ViewSet |
| | CRUD | `/api/academics/class-teacher-assignments/` | ViewSet |
| `/admin/staff` | POST | `/api/memberships/invites/` | Create invite only (no staff list API in MVP) |
| `/admin/attendance` | GET | `/api/attendance/admin/overview/` | `?date=` or `?term=` |
| `/admin/fees` | GET | `/api/finance/dashboard/collections/?term=` | Collections visibility |

---

## Teacher

| UI route | Method | Path | Notes |
|---|---|---|---|
| `/teacher` | GET | `/api/academics/my-classes/` | Class-teacher assignments |
| | GET | `/api/academics/my-assignments/` | Class-subject assignments |
| `/teacher/components` | GET | `/api/assessment/my-components/` | `?subject=&class_level=&term=` |
| | POST | `/api/assessment/components/set-scheme/` | Admin/teacher scheme |
| `/teacher/marks` | POST | `/api/assessment/scores/bulk-upsert/` | Bulk scores |
| | GET | `/api/assessment/scores/` | List/filter as needed |
| `/teacher/broadsheet` | GET | `/api/assessment/broadsheet/` | `?class_level=&arm=&term=&subject=` |
| | POST | `/api/assessment/results/recompute/` | Recompute class results |
| `/teacher/remarks` | POST/PATCH | `/api/assessment/results/remarks/` | Teacher/admin remarks |
| `/teacher/attendance` | GET | `/api/attendance/register/` | `?class_level=&arm=&term=&month=` |
| | POST | `/api/attendance/daily/bulk-upsert/` | Save register |
| | GET | `/api/academics/my-classes/` | Class picker |

---

## Bursar

| UI route | Method | Path | Notes |
|---|---|---|---|
| `/bursar` | GET | `/api/finance/dashboard/collections/?term=` | Dashboard |
| `/bursar/fee-structures` | CRUD | `/api/finance/fee-structures/` | ViewSet |
| `/bursar/payment-account` | GET/PUT/PATCH | `/api/finance/payment-account/` | Bank / Paystack subaccount |
| `/bursar/invoices` | — | — | **Gap:** no bursar invoice list endpoint; parent-only `my-invoices/`. UI may show generate result / empty until API adds list |
| `/bursar/invoices/generate` | POST | `/api/finance/invoices/generate/` | Generate for class/term |
| `/bursar/payments` | GET | `/api/finance/dashboard/collections/?term=` | Recent activity via dashboard if exposed |
| `/bursar/payments/manual` | POST | `/api/finance/payments/manual/` | Cash / bank transfer |

---

## Parent

| UI route | Method | Path | Notes |
|---|---|---|---|
| `/parent` | GET | `/api/academics/my-students/` | Linked children |
| `/parent/students` | GET | `/api/academics/my-students/` | List |
| | GET | `/api/academics/my-students/<uuid>/` | Detail placeholder |
| `/parent/results` | GET | `/api/assessment/results/student/?student=&term=` | Term results |
| | GET | `/api/assessment/report-cards/?student=&term=` | PDF |
| `/parent/attendance` | GET | `/api/attendance/summaries/student/?student=&term=` | Summary |
| | GET | `/api/attendance/parents/daily/?student=&term=` | Daily log |
| `/parent/fees` | GET | `/api/finance/my-invoices/` | Invoices |
| `/parent/fees/pay` | POST | `/api/finance/payments/initialize/` | Paystack init |
| `/parent/fees/result` | POST | `/api/finance/payments/verify/` | Verify reference |
| `/parent/more` | POST | `/api/auth/logout/` | Logout |
| `/link-student` | POST | `/api/academics/linking-codes/redeem/` | Redeem code |

---

## Platform (`apps/platform` — not the tenant app)

| UI route (platform host) | Method | Path | Scope |
|---|---|---|---|
| `/login` | POST | `/api/auth/login/` | **platform** — omit `X-Tenant-Slug` |
| `/` (revenue) | GET | `/api/platform/revenue/` | platform |
| `/tenants`, `/webhooks` | — | — | **No provision/webhook-mgmt APIs** in EMS-api MVP. UI may show informational empty states only. Do not invent endpoints. |

Paystack webhooks: `POST /api/webhooks/paystack/` on Django only — never in Next.

---

## Public / shell

| UI route | API |
|---|---|
| `/` | Landing — no API; platform card → absolute `https://{PLATFORM_HOST}` / local `http://platform.localhost:3001` |
| `/403` | Forbidden — no API |
| `/dev/ui` | Design kitchen sink — no API |
| `/dev/api-ping` | Tenant-scoped verify ping (prompt 01) |

---

## Bruno reference folders

| Domain | Bruno folder |
|---|---|
| Auth + invites | `EMS-api/bruno/Auth/` |
| Parent signup/link | `EMS-api/bruno/Parents/` |
| Academics CRUD | `EMS-api/bruno/Academics/` |
| Assessment | `EMS-api/bruno/Assessment/` |
| Attendance | `EMS-api/bruno/Attendance/` |
| Finance | `EMS-api/bruno/Finance/` |

---

## Known API gaps (do not invent)

1. No bursar/admin invoice **list** — only `invoices/generate/` + parent `my-invoices/`.
2. No staff membership **list** — invite create only.
3. No platform tenant provision / webhook admin APIs — only `GET /api/platform/revenue/`.
4. Local cross-site cookie: refresh/CSRF may fail on `*.localhost` → `localhost:8000` until a same-site local parent domain is used.
