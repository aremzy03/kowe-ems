# 02 — Auth Flows

**Goal:** Replace mock login/2FA/signup/invite with real `/api/auth/*` and memberships endpoints.

**Acceptance:** Teacher/parent login returns tokens and enters shell; admin/bursar 2FA path works; logout clears cookie + access; refresh restores session **when the refresh cookie is actually sent** (see local SameSite caveat in prompt 01). School login/2FA/refresh/logout show `X-Tenant-Slug`. Platform login does not. Invite accept uses the emailed frontend origin + path.

### Agent prompt

```
Wire auth screens to EMS-api. Remove demo role-picker as the primary path (keep a DEV-only shortcut if useful).

All SCHOOL auth calls use apiFetch scope 'tenant' (prompt 01) so X-Tenant-Slug is attached. Do not pass a tenant API host. Do not build URLs like http://testacademy.localhost:8000.

/api/auth/ is a public-path exemption in Django ONLY when neither JWT nor header is present (stays on public schema). That exists so PLATFORM login can omit the header. School login without X-Tenant-Slug 401s ("No active membership at this school." / no active account) because the view runs on public schema. Always send the header on school login, 2FA, refresh, and logout.

Implement lib/api/auth.ts:
- login(email, password) → POST /api/auth/login/ (tenant scope)
  - Response includes `role` (`admin`|`teacher`|`bursar`|`parent`|`platform_admin`)
  - If `requires_2fa: true` + `pre_auth_token` → store pre_auth only; navigate /2fa/verify (or enroll if enrollment_required)
  - Else store `access` token + `role`; navigate to role home (`/admin`, `/teacher`, `/bursar`, `/parent`)
  - Access JWT includes tenant_schema (and often role). Client still sends X-Tenant-Slug; do not parse the JWT to choose an API host.
- verify2fa(pre_auth_token, totp_code) → POST /api/auth/2fa/verify/ (tenant scope; pre_auth is JSON body, not a substitute for the tenant header)
- enroll2fa() → POST /api/auth/2fa/enroll/ ; confirm → /api/auth/2fa/enroll/confirm/ (tenant scope; Bearer pre_2fa if the API requires it — header still attached)
- refresh() → POST /api/auth/refresh/ with CSRF + credentials + tenant header for school sessions (expired refresh JWT falls through to the header)
- logout() → POST /api/auth/logout/ with CSRF + tenant header for school sessions; clear access token
- acceptInvite(payload) → POST /api/memberships/invites/accept/ (tenant scope; this path is NOT public-exempt — header required or 400)
- parentSignup(payload) → POST /api/memberships/parents/signup/ (tenant scope; same — header required or 400 / "Parent signup requires a school tenant")

Invite links (implemented Django, not Host-based API):
- Origin: TENANT_FRONTEND_ORIGIN_TEMPLATE, local default http://{slug}.localhost:3000
- Path: STAFF_INVITE_ACCEPT_PATH, default /accept-invite?token=
- UI shell mock is /invite/accept. Wire a page at the emailed path (or set STAFF_INVITE_ACCEPT_PATH to the shell route). Query param is token, not a tenant slug.
- Hostname → X-Tenant-Slug is enough for API routing.

Update (auth) pages to use react-hook-form + zod aligned to API validation errors (surface field errors from DRF).

Platform admin: login with apiFetch(..., { scope: 'platform' }) — no X-Tenant-Slug — then /platform. Do not send a school slug. Platform JWT tenant_schema is public.

Write integration notes for 2FA enroll QR (otpauth URI from API). Test against Bruno Auth folder. Note locally that refresh/logout cookies may not be sent (prompt 01).
```
