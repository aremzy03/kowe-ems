# Kowe (EMS) — Project Memory

Kowe (aka EMS, Educational Management System; from Yoruba Kọ́ wé, "write/record") is a multi-tenant SaaS school management system for Nigerian K-12 schools. It is the user's own personal project, **not** affiliated with Incel Group (the user's employer). Grounded in the user's research paper on next-generation educational management systems for Sub-Saharan Africa. Solo/small-team effort, MVP-first.

## Repo layout

Single git monorepo rooted at `ems-system/` (merged 2026-11-06 from the former separate `EMS-api` and `EMS-frontend` repos, with full history preserved under each subfolder).

- `EMS-api/` — Django backend. Phase playbooks, PRD and MVP scope live here.
- `EMS-frontend/` — npm-workspaces monorepo: `apps/tenant` (school app, `testacademy.localhost:3000`) and `apps/platform` (platform admin, `platform.localhost:3001`). See `DESIGN.md`, `PRODUCT.md`, `FRONTEND_SHELL.md`, `docs/`.

## Stack

- Backend: Django, DRF, `django-tenants`, WeasyPrint (PDFs), Paystack (payments)
- Frontend: Next.js App Router, Tailwind v4 (CSS-first config)
- Infra: Docker, CapRover, Traefik. Local Postgres on host port 5433.
- Notifications: WhatsApp
- Coding agents: Cursor and Claude Code, driven by phase playbooks

## Locked architecture decisions

- Schema-per-tenant multi-tenancy via `django-tenants`.
- **Option B**: subdomain routing lives only in the frontend. The API is a single host; tenant is resolved from the `X-Tenant-Slug` header or the JWT `tenant_schema` claim — never from `Host`.
- JWT auth with httpOnly cookie refresh tokens.
- Mandatory TOTP 2FA for admin and bursar roles.
- User identity in the shared public schema; role/profile data in tenant-scoped `SchoolMembership`.
- Paystack: one platform key with per-school subaccounts; `SubaccountTenantMap` (shared schema) routes all webhooks to a single endpoint.
- Open parent self-signup with school-issued student linking codes.

## Current state (verified against code 2026-11-05)

- Phases 0–4 built: foundation/multi-tenancy, RBAC/academic structure, grading/report cards, attendance, fees/payments.
- Phase 0.1 (Option B revision) is implemented: `HeaderTenantMiddleware` in the API; frontend API client injects `X-Tenant-Slug`.
- Frontend apps scaffolded; `apps/tenant/src/components/ui` has Button, Card, Badge, Input, Label, KpiCard, EmptyState.
- Phase 5 has a playbook (`EMS-api/EMS-Phase5-Init-Playbook.md`) but is **not built yet**.
- All data is pre-launch and disposable — no migration paths needed for architectural changes.
- Branding: name "Kowe"; logo concept C, the "Ọ Tile" (ring + subdot ọ on an indigo tile), full kit built on the Paper Brutalism palette.

Strategic note (LLM council review): real market pain exists (fee leakage, transcript delays), but over-scoping is a risk. Path: narrow wedge → real institution → then expand.

## Design system — "Paper Brutalism"

Neo-brutalism + Codecademy Gamut; flat, paper-like. Source of truth: `EMS-frontend/DESIGN.md` and `globals.css`.

- Base: warm cream `#FBF6EC` · Ink: charcoal-plum `#211F26`
- Primary: indigo-violet `#5B3DE8` · Secondary: coral `#FF7A45`
- Fonts: Space Grotesk (headings), Inter (body), JetBrains Mono (codes/IDs), Kalam (handwritten — **only** report-card signature lines and empty states)
- Border radius 8px (not 0), for approachability
- **Intensity dial**: style and shadow turned up on auth/onboarding/marketing, turned down on dashboards and dense data tables

## Ways of working

- Work is organized as phase playbooks: session primer → sequenced prompts with explicit verification steps → end-of-phase checklist. Playbooks are fed directly to Cursor or Claude Code.
- Resolve all design and architecture decisions in conversation **before** generating code prompts.
- Keep prompts modular and sequenced so each builds verifiably on the last.
- Playbook specs must reflect the actual confirmed implementation, not assumed patterns — check the code first.
- Mid-playbook corrections are expected and must propagate through the entire document, not just locally.
- Operational simplicity for a solo/small team is the primary architectural filter (this drove Option B).

## About the user

Solo/small-team developer. Prior projects on the same stack: an HRM system and an e-signature tool. Uses Cursor and Claude Code.
