# 01 — HTTP Client + Auth Storage

**Goal:** Shared API client with Bearer access token, cookie refresh, CSRF, 401 retry, and **`X-Tenant-Slug` on every tenant-scoped call (including refresh)**.

**Acceptance:**
- From `http://testacademy.localhost:3000`, `POST /api/auth/login/` hits **one** API base (`NEXT_PUBLIC_TENANT_API_URL`, e.g. `http://localhost:8000`) with `X-Tenant-Slug: testacademy` and `credentials: 'include'`. Network: Host is the API host, not `testacademy.localhost:8000`.
- Refresh (when the browser actually sends the cookie) uses the same tenant header. Retry after access expiry still includes `X-Tenant-Slug`.
- Platform-scoped calls omit `X-Tenant-Slug`.
- No `host: 'tenant' | 'platform'` URL switch. No per-school API hostname.

This prompt **owns** the HTTP client, tenant header, slug helper, and tenant-context plumbing for RSC/server fetches. Prompt 03 owns **auth** route guards only.

### Agent prompt

```
Implement the EMS API client layer in the Next.js app. UI shell already exists.

Tenant contract (match HeaderTenantMiddleware; do not guess):
- Header name: X-Tenant-Slug
- Value: first hostname label only (`testacademy`, not `testacademy.localhost`)
- Source: frontend hostname (client: window.location.hostname; server: incoming request Host / middleware-forwarded slug). Never from the API URL. Never from Host on the API.
- Attach on every scope: 'tenant' request, including login, 2FA, refresh, logout, and authenticated school APIs.
- Omit when scope is 'platform'.
- If scope is 'tenant' and slug cannot be derived, throw a clear client error — do not send the request without the header.
- Valid JWT (Bearer or refresh cookie) wins server-side; mismatched header is ignored. Still send the header so expired JWT can fall through to it.
- Do NOT select tenant by calling a per-school API hostname.

Create:
1. lib/api/config.ts
   - TENANT_API_URL from NEXT_PUBLIC_TENANT_API_URL (single fixed school API base; http://localhost:8000 or http://api.localhost:8000)
   - PLATFORM_API_URL from NEXT_PUBLIC_PLATFORM_API_URL (may equal tenant URL)
   - ROOT_DOMAIN from NEXT_PUBLIC_ROOT_DOMAIN
   - optional PLATFORM_HOST from NEXT_PUBLIC_PLATFORM_HOST
2. lib/api/tenant.ts — getTenantSlug(hostname?: string): string | null
   - `{slug}.{ROOT_DOMAIN}` → slug (lowercase)
   - null for ROOT_DOMAIN itself, PLATFORM_HOST, or unparseable hosts
3. Tenant-context plumbing (separate from auth guards):
   - Next.js middleware that reads the frontend Host, derives the slug, sets an internal request header (e.g. x-ems-tenant-slug) for RSC / Route Handlers via next/headers.
   - Must NOT redirect for auth, rewrite to a tenant API host, or pick Django schemas. Next.js cannot see the API host’s refresh_token cookie.
   - Server apiFetch reads that header (or Host) and sets X-Tenant-Slug on outbound Django calls.
   - Client apiFetch uses window.location.hostname via getTenantSlug.
4. lib/api/csrf.ts — attach X-CSRFToken on refresh/logout.
   - Login sets Django csrftoken via ensure_csrf_cookie on the API host.
   - Production: CSRF_COOKIE_DOMAIN=.yourapp.com makes document.cookie readable on schoola.yourapp.com. Use that.
   - Local: csrftoken is host-only on localhost / api.localhost; the SPA on testacademy.localhost cannot read it. Do not invent a CSRF JSON endpoint.
   - Refresh cookie is httpOnly on the API host — never read it from JS.
5. lib/auth/token-store.ts — in-memory access token (+ optional sessionStorage; document XSS). Never store refresh in JS. Separate keys from platform session (prompt 08).
6. lib/api/client.ts — apiFetch(path, { method, body, auth?: boolean, scope?: 'tenant' | 'platform' })
   - Default scope: 'tenant'
   - Base URL from scope only (two fixed URLs)
   - scope === 'tenant' → X-Tenant-Slug; scope === 'platform' → omit it
   - credentials: 'include' on login/refresh/logout/2FA cookie routes
   - Authorization: Bearer <access> when auth true
   - On 401: if detail is "Invalid tenant claim in token.", do NOT refresh-loop — clear session / show error.
   - Other 401s: single-flight POST /api/auth/refresh/ with CSRF + credentials + SAME tenant header (or platform omit), then retry once; if refresh fails → clear session → /login
   - 400 "Tenant identification required" / "Unknown tenant." → surface as client/config errors, not a refresh retry
   - Never put tenant identity in query string
7. Optional: TanStack Query QueryClientProvider with default queryFn using apiFetch (tenant scope)

Types: start with AuthTokens, ApiError { status, data }.

Implemented CORS/cookies (do not implement Django; do not assume refresh works on default local hosts):
- Django CORS_ALLOW_HEADERS already includes x-tenant-slug. Preflight OPTIONS is forced public (no tenant header required for OPTIONS).
- credentials: 'include' is required.
- Production: schoola.yourapp.com → api.yourapp.com is same-site; SameSite=Strict host-only refresh cookie is sent.
- Local: testacademy.localhost:3000 → localhost:8000 is cross-site. SameSite=Strict refresh_token WILL NOT be sent. Session restore via refresh will fail unless the human uses a same-site local parent domain (not the localhost public suffix). Document this in comments; do not invent cookie APIs or switch back to a per-school API hostname.

Do not wire login UI yet (prompt 02). Add a tiny /dev/api-ping that POSTs /api/auth/verify/ tenant-scoped (header visible in Network). Verify still benefits from the header though /api/auth/ is a public-path prefix.

Match Bruno Auth collection shapes. Insecure cookies OK locally (AUTH_COOKIE_SECURE=False).
```
