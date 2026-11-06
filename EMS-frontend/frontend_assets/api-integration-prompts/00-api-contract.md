# 00 — API Contract Overview

> Paste once. Agent should map UI routes → endpoints before writing clients.

**Owns:** hosts, env vars, tenant-header contract, endpoint map. Prompt 01 implements the client; do not implement `apiFetch` here.

### Agent prompt

```
You are wiring the EMS Next.js UI shell to EMS-api (Django + DRF + django-tenants). Do not redesign UI; replace mocks with real API calls.

Architecture (implemented Phase 0.1 — HeaderTenantMiddleware; no Host fallback):
- School UI: subdomain frontend, e.g. http://testacademy.localhost:3000 or https://schoola.yourapp.com
- API: ONE host, e.g. http://localhost:8000 or http://api.localhost:8000 (prod: https://api.yourapp.com)
- Host: testacademy.localhost on the API does NOT select a schema. Do not use testacademy.localhost:8000 as the API base.
- School requests attach header X-Tenant-Slug: <first-label> (testacademy from testacademy.localhost). Backend also accepts a full Domain or schema_name; send the first label only.
- Platform admin / Paystack webhooks: public schema; no X-Tenant-Slug.

Server resolution order (do not reimplement; the client must satisfy it):
1. Valid JWT (Authorization Bearer OR refresh_token cookie) → claim tenant_schema.
   - Missing or unknown/inactive claim → 401 {"detail": "Invalid tenant claim in token."}
   - Claim "public" stays on the public schema.
   - JWT wins; a mismatched X-Tenant-Slug is ignored.
   - Expired / malformed JWT is treated as absent (fall through). DRF still 401s the view if Bearer is required.
2. Else X-Tenant-Slug → Domain / Tenant lookup. Unknown or inactive → 400 {"detail": "Unknown tenant."}
3. Else → 400 {"detail": "Tenant identification required"}, EXCEPT:
   - OPTIONS (CORS preflight; no tenant header required)
   - Path prefixes /api/auth/, /api/platform/, /api/webhooks/ stay public if no JWT and no header

Critical: the /api/auth/ exemption is NOT permission to omit the header on school auth.
- Platform login (and other platform /api/auth/ calls): omit X-Tenant-Slug (public schema).
- School login, 2FA verify/enroll, refresh, logout: MUST send X-Tenant-Slug. Login without it runs on public schema and 401s (school user has no public membership) — not a 400.
- POST /api/memberships/invites/accept/ and POST /api/memberships/parents/signup/ are NOT under the exemption; missing header → 400 Tenant identification required.
- Send X-Tenant-Slug on every tenant-scoped call including refresh (needed when the refresh JWT is expired so middleware can fall through to the header).

Environment (fixed URLs — they do not vary per school):
- NEXT_PUBLIC_TENANT_API_URL=http://localhost:8000
  (or http://api.localhost:8000). Same value for every tenant. Never interpolate a school slug into this URL.
- NEXT_PUBLIC_PLATFORM_API_URL=http://localhost:8000
  May equal TENANT_API_URL. Scope — not hostname — decides whether the tenant header is sent.
- NEXT_PUBLIC_ROOT_DOMAIN=localhost
  Parse school slug from the frontend hostname (localhost in dev, yourapp.com in prod).
- Optional: NEXT_PUBLIC_PLATFORM_HOST if platform UI is not on a school subdomain.

How the slug is obtained (document in API_MAPPING.md; implement in prompt 01):
- Client: window.location.hostname. `{slug}.{NEXT_PUBLIC_ROOT_DOMAIN}` → first label.
- Server/RSC: incoming frontend Host (Next.js middleware / headers()), not the API URL.
- Invite emails: Django TENANT_FRONTEND_ORIGIN_TEMPLATE (local default http://{slug}.localhost:3000) + STAFF_INVITE_ACCEPT_PATH (default /accept-invite) + ?token=. The SPA reads that hostname and apiFetch attaches X-Tenant-Slug. Do not encode tenant in the invite token for API routing.
- UI shell mock route is /invite/accept; API emails /accept-invite unless STAFF_INVITE_ACCEPT_PATH is changed. Implement or rewrite to the emailed path; do not invent an API.

When X-Tenant-Slug is attached vs omitted:
- Attach on every scope: 'tenant' call (school auth including refresh/logout/2FA, memberships, academics, assessment, attendance, finance) — pre-auth AND post-auth.
- Omit on scope: 'platform' (platform admin login, /api/platform/*, webhooks are Django-only).
- If a tenant-scoped call cannot derive a slug, fail in the client. Do not send a headerless school request.

Cookies / CORS / CSRF (implemented Django; do not invent endpoints):
- Refresh cookie: host-only on the API host, path /api/auth/, SameSite=Strict by default. JS never reads it.
- Production schoola.yourapp.com → api.yourapp.com is same-site, cross-origin: Strict cookie is sent with credentials: 'include'. Set CSRF_COOKIE_DOMAIN=.yourapp.com so the SPA can read csrftoken for X-CSRFToken.
- Local testacademy.localhost:3000 → localhost:8000 (or api.localhost:8000) is CROSS-SITE (localhost is a public suffix). The Strict refresh cookie WILL NOT be sent. Same for host-only csrftoken via document.cookie. A same-site local parent domain (not *.localhost) is the honest workaround — do not invent a CSRF or cookie JSON API.
- Django already: CORS_ALLOW_HEADERS includes x-tenant-slug; CORS_ALLOW_CREDENTIALS=True; local CSRF_TRUSTED_ORIGINS includes http://*.localhost:3000; local CORS may allow all origins. Production needs CORS_ALLOWED_ORIGIN_REGEXES for school frontend subdomains.

School API prefixes (single API host + X-Tenant-Slug):
- /api/auth/ — login, refresh, logout, verify, 2fa/*  (school: header required despite public-path exemption)
- /api/memberships/ — invites/, invites/accept/, parents/signup/
- /api/academics/ — sessions, terms, class-levels, arms, subjects, students, enrollments, class-subject-assignments, class-teacher-assignments (ViewSets)
  + linking-codes/redeem/, my-students/, my-students/<uuid>/, my-assignments/, my-classes/
- /api/assessment/ — components, scores, audit-logs
  + my-components/, results/recompute/, results/student/, results/remarks/, broadsheet/, report-cards/
- /api/attendance/ — daily, audit-logs
  + summaries/student/, parents/daily/, admin/overview/, register/
- /api/finance/ — fee-structures
  + payment-account/, invoices/generate/, my-invoices/, payments/initialize/, payments/verify/, payments/manual/, dashboard/collections/

Platform (public schema, no X-Tenant-Slug):
- /api/auth/ (platform admin only)
- /api/platform/revenue/

Paystack webhooks stay on Django: POST /api/webhooks/paystack/ (no tenant header; tenant from Paystack subaccount code). Do not implement in Next.

Auth reminder: access JWT in JSON (includes tenant_schema); refresh httpOnly on API host; CSRF on refresh/logout; credentials include; school calls send X-Tenant-Slug.

Produce docs/API_MAPPING.md: each major UI page → method/path, plus a Tenant contract section (header name, slug source, omit rules, error strings above). Do not implement clients yet — wait for prompt 01.
```
