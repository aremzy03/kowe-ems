# Product Requirements Document: Multi-Tenant K-12 Educational Management System

**Status:** Draft v1 · **Owner:** Abdulmalik · **Last updated:** August 2026

---

## 1. Overview

A multi-tenant SaaS Educational Management System (EMS) for Nigerian primary and secondary schools, built as the foundation for a broader vision described in *"Engineering Next-Generation Educational Management Systems for Sub-Saharan Africa."* The MVP targets a single real pilot school on a multi-tenant architecture, so that onboarding additional schools later is a provisioning step, not a re-architecture.

Advanced capabilities from the source research — AI OCR script grading, offline-first CRDT sync, USSD payment rails, statutory API connectors (NEMIS/JAMB/NYSC) — are explicitly deferred past MVP. See §9.

---

## 2. Problem Statement

Nigerian K-12 schools rely on manual result computation, paper attendance registers, and opaque cash-based fee collection. Teachers lose significant instructional time to manual CA/result compilation; school proprietors lack real-time visibility into fee collection; parents receive academic and financial updates only via infrequent paper communication. (Full problem analysis: source research report, §"Local Operational Gaps and Institutional Bottlenecks.")

---

## 3. Goals & Non-Goals

**MVP Goals**
- Replace manual result computation with an automated, weighted CA + exam grading engine
- Give school admins real-time fee collection visibility
- Give parents digital access to results, attendance, and fee status
- Architect for multi-school onboarding from day one, without over-building for scale not yet needed

**Non-Goals (MVP)**
- AI-assisted grading of handwritten scripts
- Offline-first operation during extended connectivity loss
- Multi-campus support *within* a single school tenant
- Statutory regulatory API integrations (NEMIS/JAMB/NYSC)

---

## 4. Target Users & Roles

| Role | Scope | Core Need |
|---|---|---|
| Platform Admin | Cross-tenant | Onboard schools, manage tenant provisioning — this is Abdulmalik, not school staff |
| School Admin/Proprietor | Single tenant | Enrollment, staff, fee collection oversight |
| Teacher | Single tenant, own classes only | Mark entry, attendance |
| Bursar | Single tenant | Invoicing, payment recording, ledger |
| Parent | Single tenant (potentially multiple, see §5.2) | View child's results/attendance/fees, pay fees |

---

## 5. Architecture

### 5.1 Multi-Tenancy Model

**Decision: Schema-per-tenant via `django-tenants`, subdomain-based tenant resolution** (`schoolname.ems.incelgroup.com`).

Rationale: stronger data isolation than shared-schema (a query bug cannot leak across schools because tenants are separate PostgreSQL schemas), while remaining a single deployed codebase and single database server — no per-tenant infrastructure to provision. This also functions as a trust/compliance selling point when onboarding schools sensitive to student data handling (NDPR relevance per source research).

This is one deployed application. Onboarding a new school = create `Tenant` record → schema auto-created and migrated → create `Domain` record for the subdomain. Not a new deployment.

### 5.2 App Structure

```
SHARED_APPS (public schema, cross-tenant):
├── django_tenants       # Tenant + Domain models
├── accounts             # User model — bare identity only
└── platform_admin       # school onboarding/provisioning (Abdulmalik's tooling)

TENANT_APPS (per-school schema):
├── memberships          # SchoolMembership: role + school-specific profile, FK to shared User
├── academics             # Session, Term, ClassLevel, Arm, Subject, Enrollment
├── assessment            # AssessmentComponent, Score, ReportCard
├── attendance
├── finance               # FeeStructure, Invoice, Payment
└── communications        # NotificationLog (email/WhatsApp triggers)
```

**Key design decision:** `User` (email, password, name) lives in the shared public schema; `SchoolMembership` (role, school-specific profile) lives per-tenant with an FK back to the shared `User`. This allows one identity (e.g., a parent) to hold memberships across multiple school tenants without duplicate accounts. Cross-schema FKs work natively within a single PostgreSQL database under `django-tenants`.

### 5.3 Request Flow

1. `TenantMainMiddleware` resolves schema from subdomain, runs immediately after `SecurityMiddleware`, before JWT authentication
2. JWT authentication runs against the shared `User` table (schema-independent)
3. JWT payload carries a `school_id` claim so frontend/API logic doesn't need to infer tenant from subdomain alone
4. All subsequent ORM queries run against the resolved tenant schema automatically

### 5.4 Migrations

Two-step: `migrate_schemas --shared` (once, public schema) and `migrate_schemas --tenant` (per school schema, or targeted via `--schema=`). Must be scripted into the deploy pipeline, not run manually, before school count grows.

---

## 6. Security & Compliance

| Concern | Decision |
|---|---|
| Auth | JWT (`djangorestframework-simplejwt`); refresh token in `httpOnly`, `Secure`, `SameSite=Strict` cookie; access token in memory client-side; token rotation + blacklist on logout |
| CSRF | Required on refresh endpoint only (cookie-based); standard JWT-authenticated calls unaffected |
| RBAC | Custom role-based DRF permission classes + queryset filtering; scoped by both tenant schema (structural) and role (application-level) |
| Rate limiting | Required on auth endpoints (login, refresh) — brute-force protection |
| Audit logging | Required on grade changes: who changed what score, when, from/to what value |
| PII encryption | TLS in transit (Traefik/Let's Encrypt) + disk-level encryption baseline; field-level encryption reserved for high-sensitivity fields only if collected (e.g., national ID, medical notes) — not blanket schema encryption |
| Secrets | CapRover environment variables; never committed |
| Backups | Automated daily PostgreSQL backup (`pg_dump` → S3/Backblaze) — must cover all tenant schemas |
| Wildcard TLS | Cloudflare proxy (Universal SSL) for `*.ems.incelgroup.com`, rather than fighting CapRover's default HTTP-01 flow — deployment-phase concern, not Phase 1 blocker |

**Decisions:**
- **Parent account provisioning**: open self-signup for account creation. Access to any specific student's records requires a school-issued linking code, assigned at enrollment, entered once during or after signup. Signup alone grants no visibility into any student's data.
- **2FA**: required in MVP for admin and bursar roles (financial + grade-editing access). Not required for teacher/parent roles at MVP.
- **PDF report card generation**: WeasyPrint. Requires system-level dependencies (Pango, Cairo, GDK-PixBuf) added to the Docker image — not a pure pip install; flag this in the Dockerfile when the assessment module is built.

---

## 7. Tech Stack

**Backend:** Django 5.2, Django REST Framework, `django-tenants`, `djangorestframework-simplejwt`, `django-environ`, `django-cors-headers`, `django-ratelimit` (or DRF throttling), Celery + Redis (async: invoicing, notifications), Paystack SDK (existing skill), Sentry SDK

**Frontend:** Next.js 15 (App Router), Tailwind v4, shadcn/ui, TanStack Query, `react-hook-form` + `zod`

**Infra:** Docker Compose, CapRover, Traefik, PostgreSQL, Redis, Cloudflare DNS/proxy

**Testing:** Bruno (API collections — existing skill, extend for multi-tenant auth flows), k6 (performance — existing skill), pytest-django

---

## 8. MVP Feature Scope

### 8.1 Identity & Access Management
- Shared `User` model, JWT auth, `SchoolMembership` role model per tenant
- Role-based permission classes: admin, teacher, bursar, parent
- Open self-signup for all accounts
- Mandatory 2FA enrollment for admin and bursar roles
- `StudentLinkingCode` (tenant-scoped, in `academics`): unique code generated per student at enrollment, issued to the guardian, single-use to establish a parent `User` ↔ `Student` link. No student data is visible to a parent account until a valid code is redeemed.

### 8.2 School & Academic Structure
- Session, Term, ClassLevel, Arm, Subject
- Student profile + Guardian (linked to parent `User`)
- Enrollment (student ↔ class ↔ session/term)

### 8.3 Continuous Assessment & Grading
- Configurable weighted assessment components (1st CA, 2nd CA, Exam, etc.) per subject/class
- Score entry per student/subject/component
- Automatic term-average computation
- Broadsheet view (class × subject grid) for teachers
- Report card PDF generation with class ranking + remarks
- *Highest-priority module — primary value proposition for pilot validation*

### 8.4 Attendance
- Daily register per class/arm
- Termly summary feeding into report card

### 8.5 Fee Management
- FeeStructure per class/term
- Invoice generation per student per term
- Paystack online payment integration
- Manual payment recording (cash/bank transfer, bursar-entered)
- Collection-rate dashboard, outstanding balance ledger

### 8.6 Parent Communication
- Email + WhatsApp notification triggers: invoice generated, payment confirmed, term result published

### 8.7 Admin Dashboard
- Enrollment count, fee collection rate, attendance overview, pending mark-entry status

### 8.8 Platform Admin (Abdulmalik-facing)
- School (tenant) provisioning: create tenant, run tenant migrations, create subdomain mapping

---

## 9. Explicitly Out of Scope (Post-MVP)

- AI OCR handwritten script grading
- Offline-first PWA with IndexedDB/CRDT sync (mitigated in MVP via idempotent submit endpoints + client-side autosave, not full offline operation)
- USSD payment channels
- NEMIS/JAMB CAPS/NYSC statutory API connectors (CSV export may serve as an interim stand-in)
- CBT engine with past-question banks
- Multi-campus support within a single tenant

---

## 10. Roadmap

| Phase | Weeks | Deliverable |
|---|---|---|
| 0 | — | Multi-tenant foundation: `django-tenants` setup, shared/tenant app split, subdomain routing, tenant provisioning flow |
| 1 | 1–3 | IAM/RBAC, academic structure, student/guardian management |
| 2 | 4–6 | CA & grading engine, broadsheet, report card PDF |
| 3 | 7–8 | Attendance module |
| 4 | 9–11 | Fee management + Paystack integration, ledger, admin dashboard |
| 5 | 12–13 | Email/WhatsApp notification triggers |
| 6 | 14+ | Pilot deployment on CapRover (wildcard TLS via Cloudflare), real-school onboarding, feedback loop |

---

## 11. Success Metrics (Pilot)

- Term result compilation time reduced vs. prior manual process
- Zero cross-tenant data leakage incidents
- Fee collection visibility: real-time reconciled balance available to admin at all times
- Parent portal/notification adoption rate at pilot school
- Zero unplanned data loss (validated by backup restore test before go-live)

---

## 12. Resolved Decisions Log

| Decision | Resolution |
|---|---|
| Parent account provisioning | Open self-signup; student-record access gated by school-issued linking code assigned at enrollment |
| 2FA timing | MVP, for admin + bursar roles |
| PDF generation library | WeasyPrint |
