# 08 — Platform Integration

**Goal:** Platform admin revenue on the **public schema**. No school `X-Tenant-Slug`.

### Agent prompt

```
Wire /platform pages with apiFetch scope: 'platform' and NEXT_PUBLIC_PLATFORM_API_URL.

Public-schema rules (match HeaderTenantMiddleware):
- Never send X-Tenant-Slug on platform login, platform refresh/logout, or /api/platform/* .
- /api/auth/ and /api/platform/ are public-path prefixes: with no JWT and no header the request stays on public. That is why platform login omits the header. School UI must not reuse that omit.
- Never derive a school slug from a coincidental frontend hostname and attach it to platform calls (a school slug on platform login would resolve the SCHOOL schema and reject the platform admin for no membership).
- Do not use tenant scope for these pages even if the two env URLs are identical — scope is what omits the header.
- Platform admin JWT has tenant_schema: "public" (and role platform_admin). Treat it as a separate session from school tokens.

Calls:
- Login as platform admin via POST /api/auth/login/ with scope 'platform' (User.is_platform_admin, public schema)
- GET /api/platform/revenue/ with Bearer token, scope 'platform'
- Replace mock KPIs/table

Tenants/webhooks UI may remain partially mock if no list endpoints exist yet — only bind what the API exposes. Do not invent admin tenant-provision APIs. Do not implement Paystack webhooks in Next (POST /api/webhooks/paystack/ on Django; no tenant header; tenant from subaccount code).

Ensure platform token storage does not collide with tenant school session (separate storage keys or force logout when switching). Both may share one API host; isolation is token keys + header omit vs attach.
```
