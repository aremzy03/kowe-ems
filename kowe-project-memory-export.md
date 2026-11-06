# Kowe (EMS) — Project Memory Export

Exported 5 November 2026. Contains the four memory files for this project, verbatim.

---

## 1. overview.md
*Purpose, architecture, stack, and current build state of the multi-tenant school management SaaS. Aliases: EMS, Educational Management System, Kowe. Last updated 2026-10-12.*

### Purpose & context
- Building a multi-tenant SaaS Educational Management System (EMS) targeting Nigerian K-12 schools
- Grounded in the user's own research paper on next-generation educational management systems for Sub-Saharan Africa
- Kowe (the EMS) is the user's own project and entity, with no association with Incel Group, the company they work for
- Solo/small-team effort with an MVP-first philosophy
- An LLM council review validated the approach: genuine market pain exists (fee leakage, transcript delays), but over-scoped architecture is a risk — the recommendation was to narrow scope before expanding
- Prior projects — an HRM system and an e-signature tool — established familiarity with this stack

### Stack
- Backend: Django, DRF, `django-tenants`, WeasyPrint (PDF generation), Paystack API (payments)
- Frontend: Next.js App Router, Tailwind v4 (CSS-first config)
- Infrastructure: Docker, CapRover, Traefik
- Coding agents: Cursor and Claude Code, driven by sequenced phase playbooks
- Notifications: WhatsApp (integration in place)

### Architecture decisions (locked in)
- Schema-per-tenant multi-tenancy via `django-tenants`
- Option B decoupled architecture: subdomain routing lives at the frontend layer only; at the API level the tenant is resolved from the `X-Tenant-Slug` header or the JWT `tenant_schema` claim, not from the `Host` header
- JWT auth with httpOnly cookie-based refresh tokens
- Mandatory TOTP-based 2FA for admin and bursar roles
- User identity lives in the shared public schema; role/profile data lives in tenant-scoped `SchoolMembership`
- Paystack subaccount-based payment routing: one platform key with per-school subaccounts
- `SubaccountTenantMap` in the shared schema routes multi-tenant webhooks to a single endpoint
- Open parent self-signup with school-issued student linking codes

### Current state
- Phases 0–4 implemented: foundation/multi-tenancy, RBAC/academic structure, grading/report cards, attendance, fee/payment processing
- All existing data is pre-launch and disposable — no migration paths required for architectural changes
- A Phase 0.1 revision playbook has been drafted for the Option B shift: repurpose the `Domain` model as a lookup table, replace `TenantMainMiddleware` with custom middleware, embed tenant schema in the JWT, update invite/parent signup links, re-point Paystack webhooks to a single endpoint, update CORS config
- The Phase 0.1 playbook also specifies edits to the existing `apiFetch` wrapper in the Next.js layer: collapse to a single fixed API URL and inject the `X-Tenant-Slug` header
- UI work started: design tokens documented in `DESIGN.md`, a Tailwind v4 CSS-first `globals.css` theme file produced, and a `preview.html` demonstrating high-intensity (auth) and low-intensity (bursar dashboard) surfaces
- Phase 5 has not yet been built

### On the horizon
- Scaffold the `app/` directory structure with route groups for auth, dashboard, and parent portal
- Build a shared `components/ui` folder (Button, Card, Badge, Input) on the Paper Brutalism tokens
- Execute the Phase 0.1 revision playbook (Option B migration)
- Design and build Phase 5
- Naming the EMS "Kowe" (from Yoruba Kọ́ wé, "write/record"); chose logo concept C, the "Ọ Tile" (ring plus subdot ọ on an indigo tile), and had the full logo kit built on the Paper Brutalism palette

---

## 2. design-system.md
*The "Paper Brutalism" design system. Aliases: Paper Brutalism, DESIGN.md. Last updated 2026-09-17.*

- The design system is called "Paper Brutalism" — a hybrid of neo-brutalism and Codecademy's Gamut, evoking a flat, paper-like aesthetic
- Base color: warm cream `#FBF6EC`
- Ink color: soft charcoal-plum `#211F26`
- Primary color: indigo-violet `#5B3DE8`
- Secondary color: coral `#FF7A45`
- Headings typeface: Space Grotesk
- Body typeface: Inter
- Codes/IDs typeface: JetBrains Mono
- Kalam is the handwritten accent typeface, used strictly for report card signature lines and empty states only
- Border radius is 8px (not 0) for approachability
- Shadow intensity scales with context: higher on auth/onboarding, lower on dense data tables
- "Intensity dial" principle: style is turned up on auth/onboarding/marketing surfaces and turned down on dashboards and bulk data tables
- Design reference: neo-brutalism plus Codecademy Gamut

---

## 3. ways-of-working.md
*Playbook structure, agent workflow, and working principles. Aliases: playbooks, phase playbooks. Last updated 2026-09-17.*

- Work is organized as phase-based playbooks: session primer → sequenced prompts with explicit verification steps → end-of-phase checklist
- Playbooks are designed to be fed directly to Cursor or Claude Code
- Resolve all design and architecture decisions in conversation before generating any code prompts
- Keep prompts modular and sequenced so each builds verifiably on the last
- Playbook specs must reflect the actual confirmed implementation, not assumed patterns
- Mid-playbook corrections to assumed patterns are expected, and should propagate precisely through the entire document, not just locally
- Operational simplicity for a solo/small team is a primary architectural filter — this drove the Option B decision
- Validated path from the LLM council review: narrow wedge → real institution → then expand

---

## 4. index.md
*Project index entry. Last updated 2026-09-17.*

- Name: "Educational Manage System"
- Description: Multi-tenant SaaS school management system (Django/Next.js) for Nigerian K-12 schools
- (No further content.)
