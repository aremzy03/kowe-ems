# 09 — Hardening + Strip Mocks

**Goal:** Production-ready client behavior; mocks optional.

### Agent prompt

```
Finalize EMS frontend API integration:

1. Global error handling:
   - DRF 400 field errors → form
   - 400 {"detail": "Tenant identification required"} → client bug (missing header on a school call that is not OPTIONS); do not refresh-loop
   - 400 {"detail": "Unknown tenant."} → bad slug / inactive school; show error
   - 401 {"detail": "Invalid tenant claim in token."} → bad/missing tenant_schema on JWT; clear session, do not refresh-loop
   - Other 401 → refresh then login (prompt 01). School login without header is also 401 (public schema), not 400.
   - 403 → /403; 500 → toast
2. Loading skeletons that match neo-brutalist cards/tables (no random spinners only)
3. Empty states for my-students, invoices, assignments
4. Disable submit buttons while mutations pending
5. Set NEXT_PUBLIC_USE_MOCKS default false; delete dead mock-only routes or guard them
6. Document in the frontend README (implemented API contract, not guesses):
   - hosts file: frontend school subdomain (testacademy.localhost → 127.0.0.1); optional api.localhost. NOT a per-school API hostname
   - API on a single host (localhost:8000 or api.localhost:8000); UI on http://testacademy.localhost:3000
   - env: NEXT_PUBLIC_TENANT_API_URL (fixed), NEXT_PUBLIC_PLATFORM_API_URL (fixed, may be the same), NEXT_PUBLIC_ROOT_DOMAIN
   - X-Tenant-Slug from frontend hostname; no Host fallback on the API
   - Django local already: CORS allows x-tenant-slug; CSRF_TRUSTED_ORIGINS includes http://*.localhost:3000
   - Production: CORS_ALLOWED_ORIGIN_REGEXES for school subdomains; CSRF_COOKIE_DOMAIN=.yourapp.com
   - Refresh cookie is host-only on the API host, SameSite=Strict. Production schoola.yourapp.com → api.yourapp.com is same-site (cookie sent). Local testacademy.localhost:3000 → localhost:8000 is cross-site (cookie NOT sent) unless a same-site non-localhost parent domain is used. Do not invent cookie/CSRF endpoints.
   - Invite emails: http://{slug}.localhost:3000/accept-invite?token= (STAFF_INVITE_ACCEPT_PATH)
7. Smoke checklist aligned to Bruno phases 1–4 (auth, academics, assessment, attendance, finance), plus:
   - DevTools: school login + dashboard call + refresh all show API Host and X-Tenant-Slug: testacademy
   - platform login and revenue have no X-Tenant-Slug
   - OPTIONS preflight succeeds without requiring the tenant header
8. Confirm production-like CORS/CSRF from a school frontend origin. Locally, state honestly whether refresh cookies were sent.

Do not change the visual design system. Deliver INTEGRATION.md with known API gaps and the local cookie/CSRF caveat — do not invent endpoints to paper over them.
```
