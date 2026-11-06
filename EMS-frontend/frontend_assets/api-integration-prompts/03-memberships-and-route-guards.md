# 03 — Memberships + Route Guards

**Goal:** Real role-based routing; delete mock session cookie approach.

**Acceptance:** Wrong role hitting `/bursar` gets 403 UI; staff shell nav matches membership role. Auth middleware/guards do **not** select tenant schema or rewrite API hosts. Auth guards do **not** read `refresh_token` from the Next.js host.

### Agent prompt

```
Replace mock session with real auth session context.

1. AuthProvider: holds access token + `role` from login/2FA JSON (API already returns `role`; JWT may also contain role + tenant_schema) + display fields you keep client-side; hydrate on reload via refresh() then restore role from sessionStorage/local store (role is not a secret). No /me endpoint required for MVP guards.
   School session refresh uses tenant-scoped apiFetch (X-Tenant-Slug on refresh). Do not add host: 'tenant' here.
   Honest local caveat: refresh() needs the API-host cookie. On testacademy.localhost → localhost it will fail (cross-site Strict). Hydration may rely on persisted access until expiry; do not fake a refresh cookie on the frontend domain.
2. Staff invite create: admin UI POST /api/memberships/invites/ with email + role (from Bruno), tenant-scoped. Django emails a frontend origin (http://{slug}.localhost:3000/accept-invite?token= locally). Acceptance uses hostname → X-Tenant-Slug (prompt 02).
3. Route guards — AUTH only:
   - Next.js middleware.ts may already contain the tenant-slug forwarding helper from prompt 01 (sets x-ems-tenant-slug from frontend Host). Leave that logic untouched and do not mix it with auth.
   - Do NOT look for cookie refresh_token in Next.js middleware. That cookie is host-only on the API origin (path /api/auth/); the SPA host never receives it.
   - Prefer client guards + optional RSC that redirects if no access token on protected layouts; never trust role from query string anymore.
   - Auth middleware must NOT: attach X-Tenant-Slug to Django, pick TENANT vs PLATFORM API URL, or redirect based on school subdomain.
   - Tenant header middleware (prompt 01) must NOT: send users to /login, check roles, or block /bursar vs /admin.
4. Remove ems_mock_role. Keep mocks only behind NEXT_PUBLIC_USE_MOCKS=true for Storybook-less demos.

Ensure parent cannot open /admin; teacher cannot open finance routes.
```
