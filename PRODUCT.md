# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Monorepo: `EMS-api` (Django 5.2 + DRF + django-tenants) and `EMS-frontend` (npm workspaces: Next.js 15 App Router + TypeScript + Tailwind CSS v4). Tenant app `apps/tenant`; platform app `apps/platform`.

## Users

Equal multi-role product — no single primary persona. Confirmed audiences:

- **School admin / proprietor** — enrollment overview, staff management, fee-collection visibility, pending mark-entry status
- **Teacher** — fast mark entry, attendance register, broadsheet; scoped to own class(es) only
- **Bursar** — fee structures, invoicing, payment recording (Paystack + manual), ledger
- **Parent** — child’s results, attendance, fee balance; pay fees; self-signup gated by school-issued student linking code
- **Platform admin** — tenant/school directory and cross-tenant revenue tooling (operator-facing, not school staff). School create over HTTP is still out of scope (CLI / `create_test_tenant`).

Student self-serve is optional / post-MVP unless later confirmed.

## Product Purpose

**Kowe** is a multi-tenant Educational Management System for Nigerian primary and secondary (K–12) schools. It replaces manual result compilation, paper attendance, and opaque cash-based fee collection with digital records, weighted continuous assessment, fee visibility, and a parent portal.

Success for the MVP means: accurate fast term-result computation, real-time fee collection visibility for admins, parent digital access to results/attendance/fees, and architecture that onboards additional schools as provisioning—not re-architecture—validated on a real pilot school.

## Positioning

Schema-per-tenant multi-tenancy (`django-tenants`) with **Option B** tenant resolution (frontend subdomain + `X-Tenant-Slug` / JWT `tenant_schema`; API is a single host — never `Host`-based school selection), plus a weighted CA/exam grading engine with broadsheet and report-card PDF, fee ledger (Paystack + manual reconciliation), linking-code-gated parent access, and parent notifications (email / WhatsApp) gated by result publish. Neighboring products cannot truthfully claim the same isolation + Nigerian K–12 operating model (sessions/terms, JSS/SSS arms, ₦, WhatsApp/email parent triggers) as a single deployable SaaS.

## Operating Context

- Locale: Nigeria, English UI, currency ₦, class naming like JSS 1A, academic sessions like 2025/2026
- Local hosts: school UI `http://{slug}.localhost:3000`; platform UI `http://platform.localhost:3001`; API `http://localhost:8000`
- Auth model (API): access JWT in JSON; refresh httpOnly cookie; CSRF on refresh/logout. Admin/bursar TOTP 2FA is **deferred** (login and role gates currently skip required 2FA; re-enable via `REQUIRE_ADMIN_2FA`)
- Dense operational surfaces: mark grids, attendance registers, fee tables — must stay scannable
- Backend phases 0–5 are implemented in code (foundation through notifications). Frontend is past mock-shell: live API clients are wired; several overview surfaces still render raw JSON and need Operate UI composition

## Capabilities and Constraints

**In scope (MVP):** IAM roles above; academics (session, term, class level, arm, subject, enrollment); assessment (components, scores, broadsheet, report cards, admin publish gate); attendance; finance (fee structures, invoices, payments, collections dashboard); parent portal; communications (notification log, Celery email/WhatsApp); platform admin read surfaces (tenants, webhooks, revenue).

**Out of MVP (do not build or claim):** AI OCR grading, offline-first CRDT sync, USSD payments, NEMIS/JAMB/NYSC live connectors, CBT engine, multi-campus within one tenant; HTTP school provisioning / webhook replay from the platform UI.

**Undecided:** final production domain branding; whether student self-serve enters MVP.

## Brand Commitments

- Product name: **Kowe** (from Yoruba *Kọ́ wé*, “write/record”). **EMS** remains a technical/alias label in code and routes where useful, not the public product name.
- Logo: **Ọ Tile** kit in `kowe_brand_assets/kowe-logo-kit/` (guidelines: `KOWE-logo-guidelines.md`). App chrome uses the kit SVGs via `KoweMark` / `KoweLockup` — not a typed wordmark or hand-drawn stand-in.
- **Paper Brutalism** is the binding visual system: root `DESIGN.md`, `EMS-frontend` `globals.css` / UI kit. Ignore alternate palettes or token sets from older ui-shell prompt copy. Do not invent a competing visual world.

## Evidence on Hand

- Product/requirements: `EMS-api/EMS-PRD (1).md`, `EMS-api/EMS-MVP-Scope.md`, phase playbooks, `EMS-api/CHANGELOG.md`, `EMS-frontend/CHANGELOG.md`
- Design system: `DESIGN.md`, tenant/platform `globals.css`, UI components under `EMS-frontend/apps/*/src/components/ui`
- Brand kit: `kowe_brand_assets/kowe-logo-kit/` (SVG/PNG, `web/` favicons, presentation board)
- Backend implementation, Bruno collections, and Docker Compose in `EMS-api`
- Project memory: `kowe-project-memory-export.md`, `CLAUDE.md`
- No real pilot testimonials or customer case studies — do not fabricate them

## Product Principles

1. **Multi-role clarity** — each role sees only the job they need; RBAC boundaries are product truth, not chrome.
2. **Dense work first** — grade, attendance, and fee surfaces optimize for speed and accuracy over decoration.
3. **Pilot honesty** — ship what the Nigerian K–12 pilot can use; defer research-report vision features.
4. **Tenant trust** — school data isolation and linking-code parent access are non-negotiable.
5. **Paper Brutalism discipline** — one design authority; intensity up on auth/empty/CTAs, down on tables and money forms.

## Accessibility & Inclusion

- Minimum body text contrast 4.5:1 on paper surfaces (per DESIGN.md).
- Status is always color + label/icon (fees, attendance) — never color alone.
- Warning yellow is fill-only with dark ink text, never as text color on cream.
- Focus outlines sit outside hard offset shadows (`outline-offset: 3px`).
