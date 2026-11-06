# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 15 App Router + TypeScript + Tailwind CSS v4 (path alias `@/`). Confirmed for this greenfield frontend.

## Users

Equal multi-role product — no single primary persona. Confirmed audiences:

- **School admin / proprietor** — enrollment overview, staff management, fee-collection visibility, pending mark-entry status
- **Teacher** — fast mark entry, attendance register, broadsheet; scoped to own class(es) only
- **Bursar** — fee structures, invoicing, payment recording (Paystack + manual), ledger
- **Parent** — child’s results, attendance, fee balance; pay fees; self-signup gated by school-issued student linking code
- **Platform admin** — tenant/school provisioning and cross-tenant revenue tooling (operator-facing, not school staff)

Student self-serve is optional / post-MVP unless later confirmed.

## Product Purpose

A multi-tenant Educational Management System for Nigerian primary and secondary (K–12) schools. It replaces manual result compilation, paper attendance, and opaque cash-based fee collection with digital records, weighted continuous assessment, fee visibility, and a parent portal.

Success for the MVP means: accurate fast term-result computation, real-time fee collection visibility for admins, parent digital access to results/attendance/fees, and architecture that onboards additional schools as provisioning—not re-architecture—validated on a real pilot school.

## Positioning

Schema-per-tenant multi-tenancy (`django-tenants`, subdomain resolution) plus a weighted CA/exam grading engine with broadsheet and report-card PDF, fee ledger (Paystack + manual reconciliation), and linking-code-gated parent access. Neighboring products cannot truthfully claim the same isolation + Nigerian K–12 operating model (sessions/terms, JSS/SSS arms, ₦, WhatsApp/email parent triggers) as a single deployable SaaS.

## Operating Context

- Locale: Nigeria, English UI, currency ₦, class naming like JSS 1A, academic sessions like 2025/2026
- Backend sibling: `EMS-api` (Django 5.2 + DRF + django-tenants); tenant Host e.g. `testacademy.localhost:8000`
- Frontend build order: mock UI shell first (`frontend_assets/ui-shell-prompts`), then live API wiring (`frontend_assets/api-integration-prompts`)
- Auth model (API): access JWT in JSON; refresh httpOnly cookie; CSRF on refresh/logout; 2FA required for admin and bursar in MVP
- Dense operational surfaces: mark grids, attendance registers, fee tables — must stay scannable

## Capabilities and Constraints

**In scope (MVP / shell):** IAM roles above; academics (session, term, class level, arm, subject, enrollment); assessment (components, scores, broadsheet, report cards); attendance; finance (fee structures, invoices, payments, collections dashboard); parent portal; platform admin surfaces. Shell phase uses mock data only — no TanStack Query / live Django fetch until API integration prompts.

**Out of MVP (do not build or claim):** AI OCR grading, offline-first CRDT sync, USSD payments, NEMIS/JAMB/NYSC live connectors, CBT engine, multi-campus within one tenant.

**Undecided:** public product marketing name; final production domain branding beyond technical EMS naming.

## Brand Commitments

- No finalized product name, logo, or legal copy yet. Working label: **EMS**. Placeholder logo allowed until brand assets exist.
- **Paper Brutalism** is the binding visual system: `DESIGN.md`, `globals.css`, and `preview.html` in this repo. Ignore alternate palettes or token sets referenced in older ui-shell prompt copy (e.g. blue/cyan/yellow neo-brutalism). Do not invent a competing visual world.

## Evidence on Hand

- Product/requirements: `EMS-api/EMS-PRD (1).md`, `EMS-api/EMS-MVP-Scope.md`, phase playbooks
- Design system: `DESIGN.md`, `globals.css`, `preview.html`
- Build prompts: `frontend_assets/ui-shell-prompts/`, `frontend_assets/api-integration-prompts/`
- Backend implementation and Bruno collections in `EMS-api`
- No real pilot testimonials, logos, or customer case studies — do not fabricate them

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
