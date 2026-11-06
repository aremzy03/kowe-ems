# EMS Frontend — Integration Notes

## Implemented contract

- Single API host via `NEXT_PUBLIC_TENANT_API_URL` / `NEXT_PUBLIC_PLATFORM_API_URL`
- School UI subdomain → `getTenantSlug` → `X-Tenant-Slug` on every `scope: 'tenant'` call
- Platform UI: workspace app `apps/platform` (`@ems/platform`), `scope: 'platform'`, **never** sends `X-Tenant-Slug`
- Access JWT in memory + sessionStorage (`ems_school_*`); refresh httpOnly on API host
- CSRF on refresh/logout via readable `csrftoken` when SameSite allows

## Local cookie / CSRF caveat

`testacademy.localhost:3000` / `platform.localhost:3001` → `localhost:8000` is **cross-site** (localhost is a public suffix).

- Prefer JSON `csrfToken` from login / 2FA / `GET /api/auth/csrf/` for `X-CSRFToken` on refresh/logout — **do not** rely on `document.cookie`
- With API `LOCAL_CROSS_SITE_COOKIES=True`, refresh/CSRF cookies use `SameSite=None` so credentialed cross-site POSTs can work on local HTTP
- Without that API setting, SameSite=Strict `refresh_token` **will not** be sent from the SPA
- Production `schoola.yourapp.com` → `api.yourapp.com` is same-site; Strict cookie + readable CSRF domain work
- Do **not** invent extra CSRF endpoints beyond Django’s `GET /api/auth/csrf/`

Django local already: CORS allows `x-tenant-slug`; `CSRF_TRUSTED_ORIGINS` includes school + `http://platform.localhost:3001`.

## Error handling (client)

| Response | Behavior |
|---|---|
| 400 `Tenant identification required` | Client/config error — no refresh loop |
| 400 `Unknown tenant.` | Bad/inactive slug — surface error |
| 401 `Invalid tenant claim in token.` | Clear session — no refresh loop |
| Other 401 (authed) | Single-flight refresh, then login |
| School login without header | 401 on public schema (not 400) |

## API gaps (do not invent)

1. No bursar/admin invoice list — only generate + parent `my-invoices/`
2. No staff membership list — invite create only
3. No platform tenant provision / webhook admin APIs — only `GET /api/platform/revenue/`
4. Paystack webhooks: Django `POST /api/webhooks/paystack/` only

## Smoke checklist (Bruno-aligned)

With EMS-api running and a test tenant:

1. School login + 2FA on `testacademy.localhost:3000` — Network shows API host + `X-Tenant-Slug: testacademy`
2. `/dev/api-ping` — verify header present
3. Academics / assessment / attendance / finance flows vs Bruno phases 1–4
4. Platform login on `platform.localhost:3001` — **no** `X-Tenant-Slug`; revenue loads
5. OPTIONS preflight succeeds without tenant header
6. Locally: note whether refresh cookie was sent (often no)

## Invite path

Emails: `http://{slug}.localhost:3000/accept-invite?token=`  
Shell legacy `/invite/accept` redirects to `/accept-invite`.
