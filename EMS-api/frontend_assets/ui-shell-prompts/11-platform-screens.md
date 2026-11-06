# 11 — Platform Screens (Mock Data)

**Goal:** Quiet platform-admin surfaces (public/platform schema — not a school tenant).

**Acceptance:** `/platform` revenue + tenants + webhook logs with mocks; quieter neo-brutalism.

### Agent prompt

```
Implement Platform Admin under app/(platform) with a simple top nav (Revenue, Tenants, Webhooks) — not the school staff sidebar.

Pages:
1. /platform — Revenue KPIs (volume, commission, active schools) + per-tenant table
2. /platform/tenants — school list with schema/subdomain mono (testacademy)
3. /platform/webhooks — log table time/event/tenant/status + detail drawer

lib/mocks/platform.ts. Dial neo-brutalism DOWN–MEDIUM; primary blue for chrome; yellow CTA rare.
When done, add a short FRONTEND_SHELL.md in the frontend repo summarizing routes, mocks, and that API wiring is next (api-integration-prompts).
```
