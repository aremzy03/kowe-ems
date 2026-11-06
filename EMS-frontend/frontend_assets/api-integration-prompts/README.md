# EMS — API Integration Prompts (Frontend Agent)

Prompts for a coding agent to **replace mock data** in an existing Next.js EMS UI shell with the real Django EMS-api.

## Prerequisites

- UI shell complete (see [`../ui-shell-prompts/`](../ui-shell-prompts/))
- EMS-api running on a **single** API host (e.g. `http://localhost:8000` or `http://api.localhost:8000`) — not a per-school API hostname
- School UI served on a **frontend subdomain** (e.g. `http://testacademy.localhost:3000`)
- Bruno collection under `EMS-api/bruno/` as behavioral reference

## Auth + tenant model (read before coding)

| Piece | Behavior |
|---|---|
| Access token | JWT in JSON → memory (optional short-lived persistence); `Authorization: Bearer`. Claim **`tenant_schema`** (school schema name, or `public` for platform admin). Also may include `role`. |
| Refresh token | **httpOnly cookie** `refresh_token` on path `/api/auth/` — not readable by JS. **Host-only on the API host**, not the frontend subdomain. Default SameSite=Strict. |
| CSRF | Required on `POST /api/auth/refresh/` and `POST /api/auth/logout/` (`X-CSRFToken` matching `csrftoken`) |
| Tenant (school) | Frontend stays subdomain-based. API is **one host**. **No Host fallback** — `Host: testacademy.localhost` does not select a schema. School calls attach **`X-Tenant-Slug: testacademy`** (first label of the frontend hostname). |
| Resolution (server) | (1) Valid JWT (Bearer **or** refresh cookie) → `tenant_schema`. Missing/unknown claim → **401** `Invalid tenant claim in token.` Claim `public` stays public. JWT wins; a mismatched header is **ignored**. Expired JWT is treated as absent → fall through. (2) Else header → Domain/schema lookup. Unknown/inactive → **400** `Unknown tenant.` (3) Else **400** `Tenant identification required`, except OPTIONS preflight and public-path prefixes `/api/auth/`, `/api/platform/`, `/api/webhooks/` (those stay public if no JWT/header). |
| `/api/auth/` exemption | Does **not** mean school auth can omit the header. Platform login omits it (public schema). **School** login, 2FA, refresh, logout **must** send `X-Tenant-Slug`. School login without it runs on public schema and **401**s (no school membership) — it is not a 400. Memberships signup/invite-accept are **not** exempt: missing header → 400. |
| Platform | Public schema. `scope: 'platform'`. **Omit** `X-Tenant-Slug`. Platform JWT has `tenant_schema: public`. |
| 2FA | Admin/bursar: login may return `requires_2fa` + `pre_auth_token` → `/api/auth/2fa/verify/` or enroll. Still tenant-scoped (header). |

Send `X-Tenant-Slug` on **every tenant-scoped call, including refresh**.

Frontend must use `credentials: 'include'` so the API-host refresh cookie *can* be sent. Production `schoola.yourapp.com` → `api.yourapp.com` is **same-site** (Strict OK). Local `testacademy.localhost:3000` → `localhost:8000` is **cross-site**; Strict refresh cookie **will not be sent**. Django CORS already allows `x-tenant-slug`; local CSRF already trusts `http://*.localhost:3000`. Do not invent a CSRF/cookie endpoint.

**Do not conflate Next.js middlewares:** auth route guards (prompt 03) are about session/role. Tenant slug extraction / `X-Tenant-Slug` (prompt 01) is a separate concern. Next.js middleware **cannot** see the API host’s `refresh_token` cookie.

## How to run

1. Paste prompts **in order** (`00` → `09`).
2. After each domain, smoke-test with the matching Bruno folder.
3. Remove or gate mock session once real auth works.

## Prompt index

| # | File | Focus |
|---|---|---|
| 00 | `00-api-contract.md` | Single API host, env, `X-Tenant-Slug` contract, endpoint map |
| 01 | `01-http-client-and-auth-storage.md` | `apiFetch`, tenant header, tenant-context middleware, refresh queue, CSRF |
| 02 | `02-auth-flows.md` | Login, 2FA, logout, invite, parent signup |
| 03 | `03-memberships-and-route-guards.md` | Role from membership; **auth** guards (not tenant routing) |
| 04 | `04-academics.md` | Sessions→enrollment, parent linking, teacher assignments |
| 05 | `05-assessment.md` | Components, scores, broadsheet, PDF |
| 06 | `06-attendance.md` | Register, summaries, admin overview |
| 07 | `07-finance.md` | Fees, invoices, Paystack, manual pay |
| 08 | `08-platform.md` | Public-schema revenue; no school tenant header |
| 09 | `09-hardening.md` | Errors, empty states, strip mocks |
