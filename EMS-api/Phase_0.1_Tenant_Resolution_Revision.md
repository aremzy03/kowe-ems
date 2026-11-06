# Phase 0.1 — Tenant Resolution Architecture Revision

**Status:** Pre-launch, disposable data. Clean swap — no migration path required.
**Supersedes:** Host-header-based tenant resolution introduced in Phase 0.
**Touches:** Phase 0 (middleware), Phase 1 (JWT, invite/signup links), Phase 4 (Paystack webhooks), CORS config across all phases, and the Next.js API integration layer (`apiFetch` wrapper, Prompt 01) and local dev README — host-based tenant resolution is baked into the frontend client itself, not just the Django middleware.
**Does not touch:** Phase 2 (grading/report cards), Phase 3 (attendance) — these operate on `request.tenant` / the active schema connection regardless of how it was set.

---

## 0. Goal

Move from **API-level subdomain tenancy** (`django-tenants`' default `TenantMainMiddleware`, which resolves the schema from the `Host` header) to:

- **Frontend:** stays subdomain-based (`schoola.yourapp.com`, `schoolb.yourapp.com`) — purely for branding/routing, unchanged.
- **API:** single domain (`api.yourapp.com`). Tenant is resolved explicitly per request via:
  - A custom header (`X-Tenant-Slug`) for **pre-auth** requests (login, signup, invite acceptance).
  - A `tenant_schema` claim embedded in the **JWT** for all authenticated requests post-login.

`django-tenants`' schema-per-tenant machinery is unchanged — only *how the active schema gets identified per request* changes.

**Confirmed current state (not an assumption):** host-based resolution is the actual implementation on both sides, not just `TenantMainMiddleware` defaulting to it:

- The README instructs hitting the tenant host directly (`http://testacademy.localhost:8000`), not bare `localhost` — `Host` selects the schema.
- Prompt 01's `apiFetch(..., { host?: 'tenant' | 'platform' })` picks between `NEXT_PUBLIC_TENANT_API_URL` and `NEXT_PUBLIC_PLATFORM_API_URL` as the base URL — no tenant header is set anywhere.
- Prompt 03's middleware only guards auth routes (httpOnly refresh); it plays no role in tenant routing.

So this revision has **three** surfaces to change, not one: the Django middleware, the `apiFetch` wrapper's routing logic, and the README's dev instructions. Section 5 below replaces the `host: 'tenant' | 'platform'` URL-switching pattern with header injection on a single tenant API base URL.

---

## 1. Domain model — keep it, repurpose it

The existing `Domain` model (from `django-tenants`) does **not** need to be dropped. Repurpose its role:

- **Before:** used by `TenantMainMiddleware` to map `Host` → schema automatically.
- **After:** used as a lookup table to validate/resolve a `tenant_slug` string → schema name, called explicitly by your custom middleware instead of implicitly by `django-tenants`.

No schema changes required here — only what queries against it and when.

---

## 2. Custom tenant resolution middleware (replaces `TenantMainMiddleware`)

Build a middleware that runs early in `MIDDLEWARE`, replacing `django_tenants.middleware.main.TenantMainMiddleware`.

**Resolution order per request:**

1. **If the request carries a valid JWT** (post-auth): decode it, read the `tenant_schema` claim, call `connection.set_schema(tenant_schema)` (or `set_schema_to_public()` fallback if claim is missing/invalid — treat as an auth error, not a silent public-schema fallback).
2. **If no JWT (pre-auth: login, parent signup, invite acceptance):** read the `X-Tenant-Slug` header, look it up against the `Domain`/tenant table, resolve the schema, call `connection.set_schema(...)`.
3. **If neither is present:** reject with a clear 400 (`Tenant identification required`) rather than falling through to public schema — this avoids silent cross-tenant leakage bugs during the transition.

**Verification step:** write a test that hits an authenticated endpoint with (a) a valid JWT for Tenant A, (b) no header/claim at all, (c) a malformed `X-Tenant-Slug`. Only (a) should succeed.

---

## 3. JWT structure changes

Update JWT issuance (login endpoint, and wherever refresh tokens are re-issued) to embed:

```json
{
  "user_id": "...",
  "tenant_schema": "schoola",
  "role": "...",
  ...
}
```

Since this is pre-launch with disposable data, **do not** build backward-compatibility handling for tokens issued under the old scheme — just change the payload and re-issue. Any existing test sessions will need to log in again.

**Verification step:** decode a freshly issued token and confirm `tenant_schema` is present and correct for the login used.

---

## 4. Invite links & parent signup links

These currently likely encode tenant identity via the subdomain the link points to (e.g., `schoola.yourapp.com/invite/abc123`). Decide between two options:

- **Keep link-based tenant resolution (recommended, least rework):** the link still points at the tenant's frontend subdomain. The frontend page at that subdomain reads its own hostname and passes it into `apiFetch` so the header gets attached when it calls the API to accept the invite/complete signup. No change to link generation — only to what `apiFetch` does with that hostname once the page loads (Section 5).
- **Fully explicit (more rework, not necessary here):** encode `tenant_slug` directly inside the invite/signup token itself, independent of the link's hostname.

**Recommendation:** go with the first option — it reuses your existing link generation logic entirely and only changes how `apiFetch` identifies the tenant on the request it makes (Section 5 covers this).

**Verification step:** generate a staff invite and a parent signup link for a test tenant, walk through acceptance end-to-end, confirm the created user lands in the correct schema.

---

## 5. Frontend: retire `host: 'tenant' | 'platform'` URL-switching, add header injection

This is the section that changes most given the confirmed current implementation. Two concrete edits to Prompt 01's `apiFetch` and its surrounding setup:

**a) Environment/base URL:**
- `NEXT_PUBLIC_PLATFORM_API_URL` stays as-is — platform-level (non-tenant) endpoints were never subdomain-routed, so nothing changes there.
- `NEXT_PUBLIC_TENANT_API_URL` collapses from "a pattern that resolves per-subdomain" (`testacademy.localhost:8000`-style) to a single fixed value: `api.yourapp.com` (or `api.localhost:8000` in dev). It no longer varies by tenant.

**b) `apiFetch` signature and behavior:**
- Drop the `host?: 'tenant' | 'platform'` base-URL-selection role — it's no longer picking between hostnames per tenant, since there's only one tenant API host now. Keep a `scope?: 'tenant' | 'platform'` param if useful for picking between the two *fixed* base URLs (tenant vs platform), but decouple that from tenant identity entirely.
- Add tenant identity as an explicit input to `apiFetch`: either read it from `window.location.hostname` (client-side calls) or from a value threaded down from `middleware.ts` (Server Components/Route Handlers), and attach it as `X-Tenant-Slug: <subdomain>` on every outgoing request to the tenant API base URL — pre-auth and post-auth alike. Post-auth, the JWT claim takes precedence server-side, but sending the header regardless keeps the client logic uniform and covers the pre-auth login/signup/invite-acceptance calls that have no JWT yet.
- `middleware.ts` (Prompt 03) does not need new tenant-routing responsibility — it can stay scoped to auth route guards. Tenant subdomain extraction can live directly in `apiFetch`'s call sites or a small shared helper, since it's just reading `window.location.hostname` / the request's `Host` header, not making routing decisions.

**c) README update:** replace the "hit the tenant host, not bare localhost" instruction with: run the API on a single dev host (`api.localhost:8000` or similar), keep frontend dev subdomains as they are (`testacademy.localhost:3000`), and note that `apiFetch` now handles tenant identification via header, not via which host you're hitting.

**Verification step:** confirm requests from `testacademy.localhost:3000` (or `schoola.yourapp.com`) reach the single API host with `X-Tenant-Slug: testacademy` in dev tools' network tab, both for an unauthenticated login call and an authenticated dashboard call — and confirm platform-scoped calls are unaffected.

---

## 6. Paystack webhook re-pointing (Phase 4 — highest risk area)

- **Before:** webhook likely registered per-tenant-subdomain, e.g. `schoola.yourapp.com/api/webhooks/paystack/`, tenant resolved via host.
- **After:** single endpoint, `api.yourapp.com/api/webhooks/paystack/`. Resolve tenant from the **subaccount code** present in the Paystack payload (`data.subaccount.subaccount_code` or equivalent field depending on event type) — look this up against your stored subaccount-to-tenant mapping to determine the schema before processing the event.

Since these are test subaccounts on disposable data, there's no live re-registration risk — just update the registered webhook URL in the Paystack dashboard for your test integration and update the endpoint's tenant-resolution logic.

**Verification step:** trigger a test `charge.success` webhook from Paystack's dashboard, confirm it resolves to the correct tenant schema and records the payment against the correct invoice.

---

## 7. CORS configuration

- **Before:** likely permissive/wildcard CORS to accommodate `*.api.yourapp.com` matching `*.yourapp.com`.
- **After:** single API origin, so CORS becomes a straightforward allow-list of frontend origins: `https://*.yourapp.com` (or an explicit list if you're not comfortable with wildcard origin matching — Django's `django-cors-headers` supports regex-based `CORS_ALLOWED_ORIGIN_REGEXES` for this).

**Verification step:** confirm a request from `schoolb.yourapp.com` to `api.yourapp.com` succeeds, and a request from an arbitrary non-matching origin is rejected.

---

## 8. Regression sweep

Search the codebase for any remaining assumptions of host-based tenant resolution that Phases 1–4 may have introduced independently of the core middleware:

```bash
grep -rn "get_host\|request.tenant\|TenantMainMiddleware\|HTTP_HOST" --include="*.py"
grep -rn "NEXT_PUBLIC_TENANT_API_URL\|host: 'tenant'\|host: \"tenant\"\|testacademy.localhost" --include="*.ts" --include="*.tsx"
```

Check each hit against: does this still make sense under explicit resolution, or was it silently relying on `django-tenants`' automatic host-based behavior (backend) or the `host: 'tenant' | 'platform'` URL switch (frontend)?

Particular areas to check given what's been built:
- Audit logging (Phase 2) — if it logs `request.get_host()` anywhere for context, that's now less meaningful (single API host) and may want `tenant_schema` logged explicitly instead.
- Any admin/reporting endpoint that assumed "current host tells you the tenant" for display purposes.
- Any frontend call site that constructs a tenant subdomain URL directly instead of going through `apiFetch` — those will silently keep hitting the old per-tenant host pattern unless updated.
- README and any onboarding/setup docs that still reference `testacademy.localhost:8000` as the API host to hit.

---

## 9. End-of-phase checklist

- [ ] `TenantMainMiddleware` removed from `MIDDLEWARE`, custom middleware in place
- [ ] JWT payload includes `tenant_schema`; login flow tested end-to-end
- [ ] Pre-auth endpoints (login, signup, invite acceptance) correctly resolve tenant from `X-Tenant-Slug`
- [ ] `apiFetch` (Prompt 01) no longer switches base URL by tenant; attaches `X-Tenant-Slug` on every tenant-scoped call instead
- [ ] `NEXT_PUBLIC_TENANT_API_URL` collapsed to a single fixed value; no per-subdomain variation remains
- [ ] README updated to drop "hit the tenant host" instruction in favor of single API host + header
- [ ] Invite and parent signup links tested end-to-end against new resolution path
- [ ] Paystack webhook re-pointed to single endpoint; tenant resolved from subaccount code; test `charge.success` verified
- [ ] CORS updated to single-API-origin allow-list; cross-subdomain frontend requests verified
- [ ] Regression grep completed; no orphaned `get_host()`/host-based assumptions remain
- [ ] Old per-tenant test schemas either cleaned up or consciously left as disposable clutter
