# Nigerian K-12 EMS — MVP Scope & Technical Plan

**Target:** Primary & Secondary schools · **Client:** real pilot school · **Stack:** Django 5.2 + DRF, Next.js 15, PostgreSQL, JWT auth, CapRover deployment

This scopes down the full research report into a buildable MVP. The MVP proves the core value (accurate, fast result computation + fee visibility + parent communication) on one real school before layering in AI OCR, offline sync, and statutory connectors.

---

## 1. Design Principle: MVP vs. Full Vision

The research report describes six microservices and an offline-first CRDT sync engine. Building that first would take months before a single real user touches it. Instead:

| Research Report Component | MVP Decision |
|---|---|
| IAM/RBAC | **Build now** — foundational, cheap to get right early |
| Academic Records & CA Service | **Build now** — this is the core value proposition |
| Financial Settlement Service | **Build now, simplified** — Paystack + manual reconciliation, skip USSD/split-settlement |
| Omnichannel Communication | **Build now, minimal** — email + WhatsApp (you already have this skill) |
| Multimodal AI OCR & Assessment | **Defer** — needs volume of real scripts to tune against; premature for one pilot school |
| Offline-First Sync (IndexedDB/CRDT) | **Defer, mitigate instead** — see §5 |
| Statutory Connector Gateway (NEMIS/JAMB/NYSC) | **Defer** — not applicable to K-12 in the same way; NEMIS export can be a later CSV export feature, not a live API |

A single real school is your validation loop. Better to ship a tight, reliable core and expand based on what the pilot actually needs than to guess at six months of infrastructure up front.

---

## 2. Stakeholders & Roles (MVP)

| Role | Core Need |
|---|---|
| Admin/Proprietor | Enrollment overview, fee collection visibility, staff management |
| Teacher | Fast mark entry, attendance, view own class(es) only |
| Bursar | Fee invoicing, payment recording, ledger |
| Parent | View child's results, attendance, fee balance, pay fees |
| Student *(optional in MVP)* | View own results — can be deferred to Phase 2 if time-constrained |

RBAC boundaries matter from day one: a teacher should never see bursary data, and a bursar should never edit grades — this is cheap to enforce now and expensive to retrofit.

---

## 3. MVP Module Breakdown

### 3.1 Identity & Access Management
- Custom `User` model (UUID pk, matching your HRM pattern), role field: `admin`, `teacher`, `bursar`, `parent`
- JWT auth (SimpleJWT) — reuse your Bruno collection patterns from `incel-hrm`/`incel-esign`
- Role-based permission classes in DRF (per-object filtering, not just per-view)

### 3.2 School & Academic Structure
- `Session` (academic year), `Term` (1st/2nd/3rd)
- `ClassLevel` + `Arm` (e.g., JSS1, JSS1A/JSS1B)
- `Subject`, `ClassSubjectAssignment` (which teacher teaches what to which arm)
- `Student` profile + `Guardian` (linked to parent User)
- `Enrollment` (student ↔ class ↔ session/term)

### 3.3 Continuous Assessment & Grading
- `AssessmentComponent` (e.g., 1st CA, 2nd CA, Exam) with configurable weighting per subject/class
- `Score` entry per student/subject/component
- Automatic term-average computation against the weighting scheme
- Broadsheet view (class × subject grid) for teachers
- Report card generation (PDF) — position-in-class ranking, teacher/principal remarks
- This is the single highest-value module — it's the "80% reduction in result compilation time" claim from the report, and the easiest to validate with a real school immediately

### 3.4 Attendance
- Daily register per class/arm
- Termly attendance summary feeding into the report card

### 3.5 Fee Management (simplified Financial Settlement Service)
- `FeeStructure` per class/term (tuition, PTA, other levies)
- `Invoice` generation per student per term
- Paystack integration for online payment — **you already have this skill built**, reuse it directly
- Manual payment recording for cash/bank transfer (bursar-entered, since not every parent will pay online at a pilot school)
- Simple ledger: paid vs. outstanding per student, collection-rate dashboard for admin

### 3.6 Parent Communication (minimal Omnichannel Service)
- Email notification on: invoice generated, payment confirmed, term result published
- WhatsApp notification for the same triggers — **you already have this skill built**, reuse for OTP-style parent alerts
- Skip: USSD, SMS gateway (add later if the pilot school's parents need it — many will have WhatsApp)

### 3.7 Admin Dashboard
- Enrollment count, fee collection rate, attendance overview, pending mark-entry status per class

---

## 4. Explicitly Out of MVP Scope (Phase 2+)

- AI OCR handwritten script grading (needs real script volume from the pilot to be worth building)
- Offline-first PWA with IndexedDB + CRDT sync
- USSD payment channels
- NEMIS/statutory API connectors (CSV export is a fine stand-in for now)
- Multi-campus / multi-tenant architecture
- CBT engine with past-question banks

---

## 5. Offline Risk — Mitigate Without Full CRDT Sync

The report is right that connectivity/power drops are a real risk during mark entry. Full CRDT sync is overkill for one school's data volume. A lighter mitigation for MVP:

- Frontend: persist in-progress mark entry to browser `localStorage`/component state with periodic autosave attempts, so a dropped connection doesn't lose an unsaved page of marks
- Backend: idempotent score-submission endpoint (submit by `student_id + subject_id + component_id`, upsert not append) so retries after reconnect are safe
- This gets you real resilience without building a distributed sync engine for a single-school pilot

---

## 6. Suggested Django App Structure

```
ems/
├── accounts/        # IAM, custom User, RBAC
├── academics/       # Session, Term, ClassLevel, Arm, Subject, Enrollment
├── assessment/      # AssessmentComponent, Score, ReportCard generation
├── attendance/      # DailyAttendance
├── finance/         # FeeStructure, Invoice, Payment (Paystack)
├── communications/  # NotificationLog (email/WhatsApp triggers)
└── core/            # shared utils, permissions, pagination
```

Frontend: Next.js 15 app router, mirroring your `incel-hrm` structure — role-based dashboards (`/admin`, `/teacher`, `/bursar`, `/parent`).

---

## 7. Realistic MVP Roadmap

| Phase | Weeks | Deliverable |
|---|---|---|
| 1 | 1–3 | IAM/RBAC, academic structure, student/guardian management |
| 2 | 4–6 | CA & grading engine, broadsheet, report card PDF generation |
| 3 | 7–8 | Attendance module |
| 4 | 9–11 | Fee management + Paystack integration, ledger, admin dashboard |
| 5 | 12–13 | Email/WhatsApp notification triggers |
| 6 | 14+ | Pilot deployment on CapRover, real-school onboarding, feedback loop |

This is deliberately sequenced so the highest-value module (grading) ships before the harder-to-validate ones (finance, comms) — you want a teacher at the pilot school entering real marks as early as possible.

---

## 8. Next Step

The natural next move, matching how you built the HRM leave module, is a Cursor AI prompt playbook for **Phase 1 (accounts + academics apps)** — model definitions, migrations, DRF serializers/viewsets, and RBAC permission classes. Want me to draft that playbook next?
